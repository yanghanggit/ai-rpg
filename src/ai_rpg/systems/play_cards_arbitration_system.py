"""战斗仲裁动作系统模块。"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    collect_target_character_stats,
    compute_character_stats,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HumanMessage,
    PlayCardsAction,
    RoundStatsComponent,
    StageDescriptionComponent,
)
from ..utils import extract_json
from .arbitration_prompt_builders import (
    ArbitrationResponse,
    build_combat_arbitration_broadcast,
    build_combat_arbitration_prompt,
    build_condensed_combat_arbitration_prompt,
    build_stats_update_notification,
)


###########################################################################################################################################
@final
class PlayCardsArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction 事件，对单张出牌立即进行 AI 仲裁结算。"""

    def __init__(self, game: DBGGame, use_condensed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._use_condensed_prompt: Final[bool] = use_condensed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction) and entity.has(RoundStatsComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("PlayCardsArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        logger.debug(
            f"PlayCardsArbitrationSystem: 触发仲裁，找到 {len(entities)} 个符合条件的出牌实体"
        )

        # for entity in entities:
        await self._request_combat_arbitration(entities[0])

    #######################################################################################################################################
    async def _request_combat_arbitration(self, actor_entity: Entity) -> None:

        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, f"无法获取 {actor_entity.name} 所在场景实体！"

        """驱动单次出牌的完整仲裁流程。"""
        assert actor_entity.has(
            PlayCardsAction
        ), f"实体 {actor_entity.name} 缺少 PlayCardsAction 组件！"
        play_cards_action = actor_entity.get(PlayCardsAction)

        assert actor_entity.has(
            RoundStatsComponent
        ), f"出牌实体 {actor_entity.name} 缺少 RoundStatsComponent！"

        # dict.fromkeys 去重并保序（SPREAD 的 targets 长度=hit_count，可能含重复名）
        # 获取目标实体的当前属性、装备附加属性，用于生成仲裁提示
        target_stats = collect_target_character_stats(
            self._game, play_cards_action.targets
        )

        # 获取当前回合数，用于仲裁提示生成
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 获取最新回合的行动信息，供仲裁提示词扩展使用
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "仲裁阶段最新回合不应为 None"
        round_action_order = latest_round.action_order
        round_completed_actors = latest_round.completed_actors
        round_current_actor = latest_round.current_actor

        assert stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"
        current_stage_description = stage_entity.get(
            StageDescriptionComponent
        ).narrative

        # 生成仲裁提示消息，包括出牌实体、目标实体的状态效果和装备附加属性等信息
        message = build_combat_arbitration_prompt(
            actor_entity.name,
            compute_character_stats(actor_entity),
            play_cards_action.card,
            play_cards_action.targets,
            target_stats,
            current_round_number,
            current_stage_description,
            play_cards_action.gear_item,
            round_action_order,
            round_completed_actors,
            round_current_actor,
        )

        # 生成精简后的仲裁提示消息，用于在需要时向 LLM 提供更简洁的上下文信息
        condensed_message = (
            build_condensed_combat_arbitration_prompt(
                actor_entity.name,
                compute_character_stats(actor_entity),
                play_cards_action.card,
                play_cards_action.targets,
                target_stats,
                current_round_number,
                current_stage_description,
                play_cards_action.gear_item,
                round_action_order,
                round_completed_actors,
                round_current_actor,
            )
            if self._use_condensed_prompt
            else None
        )

        # 初始化 DeepSeekClient，用于与 LLM 进行交互，传入生成的仲裁提示消息和精简提示消息（如果启用）
        chat_client = DeepSeekClient(
            name=stage_entity.name,
            full_prompt=message,
            condensed_prompt=condensed_message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,
        )

        # 发起 LLM 请求，捕获异常以防止整个流程崩溃
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(f"[PlayCardsArbitrationSystem] LLM 请求失败: {e}")
            return

        # 检查 LLM 是否返回了有效的响应内容，如果为空则记录错误并返回
        if chat_client.response_ai_message is None:
            logger.error("[PlayCardsArbitrationSystem] LLM 返回空响应")
            return

        # 解析 LLM 的响应内容，提取 JSON 并转换为 ArbitrationResponse 对象，供后续处理使用
        self._apply_arbitration_result(chat_client, actor_entity)

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
    ) -> None:
        """解析 AI 仲裁响应，更新 HP，广播仲裁事件，写入回合记录。解析失败仅记录 error。"""

        if chat_client.response_ai_message is None:
            logger.error("[PlayCardsArbitrationSystem] LLM 回复内容为空")
            return

        # 获取当前行动者所在的场景实体，确保后续的仲裁结果能够正确应用到对应的场景上下文
        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert (
            stage_entity is not None
        ), f"PlayCardsArbitrationSystem: 无法获取 {actor_entity.name} 所在场景实体！"

        try:

            # 解析 LLM 返回的 JSON 响应，构建 ArbitrationResponse 对象，用于后续的游戏状态更新和广播处理
            format_response = ArbitrationResponse.model_validate_json(
                extract_json(chat_client.response_content)
            )

            # 验证 final_stats 中的实体名称是否存在于游戏中
            for entity_name, entity_stats in format_response.final_stats.items():
                if self._game.get_entity_by_name(entity_name) is None:
                    raise ValueError(
                        f"final_stats 中的实体不存在于游戏中: {entity_name}"
                    )

        except Exception as e:
            logger.error(f"Exception: {e}")
            return

        # 仲裁者（combat stage）更新自身场景环境快照
        if format_response.stage_description.strip():
            stage_entity.replace(
                StageDescriptionComponent,
                stage_entity.name,
                format_response.stage_description,
            )

        # 根据是否使用精简提示，添加上下文。
        if self._use_condensed_prompt:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(
                    content=chat_client.condensed_prompt,
                    full_prompt=chat_client.full_prompt,
                ),
            )
        else:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(content=chat_client.full_prompt),
            )

        # 将 AI 的响应消息添加到游戏上下文中，便于后续的回合记录和状态更新。
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=chat_client.response_ai_message,
        )

        # 广播当前回合的仲裁结果，包括战斗日志和叙事内容，通知场景中的所有实体（除当前场景实体外）
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=build_combat_arbitration_broadcast(
                    format_response.combat_log,
                    format_response.narrative,
                    current_round_number,
                    actor_entity.name,
                ),
                stage=stage_entity.name,
                combat_log=format_response.combat_log,
                narrative=format_response.narrative,
            ),
            exclude_entities={stage_entity},
        )

        # 更新每个实体在仲裁后的 HP 状态，并记录状态效果的变化，确保游戏状态与仲裁结果保持一致。
        for entity_name, entity_stats in format_response.final_stats.items():

            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到 final_stats 中的实体: {entity_name}"

            assert entity.has(
                CharacterStatsComponent
            ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"

            old_hp = compute_character_stats(entity).hp
            after_stats = set_character_hp(entity, int(entity_stats.hp))
            new_hp = after_stats.hp
            max_hp = after_stats.max_hp
            logger.info(f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}")

            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=build_stats_update_notification(new_hp, max_hp)
                ),
            )

        # 将本回合的战斗日志和叙事内容添加到当前回合的记录中，便于后续回合的回顾和游戏状态的追踪。
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.cards_combat_log.append(format_response.combat_log)
        latest_round.cards_narrative.append(format_response.narrative)

    #######################################################################################################################################
