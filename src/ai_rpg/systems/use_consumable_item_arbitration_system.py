"""使用消耗品仲裁系统模块。"""

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
    StageDescriptionComponent,
    UseConsumableItemAction,
)
from ..utils import extract_json
from .arbitration_prompt_builders import (
    ArbitrationResponse,
    build_condensed_consumable_arbitration_prompt,
    build_consumable_arbitration_broadcast,
    build_consumable_arbitration_prompt,
    build_stats_update_notification,
)


#######################################################################################################################################
@final
class UseConsumableItemArbitrationSystem(ReactiveProcessor):
    """响应 UseConsumableItemAction 事件，调用 LLM 仲裁消耗品效果（HP/状态效果描述更新）。"""

    def __init__(self, game: DBGGame, use_condensed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._use_condensed_prompt: Final[bool] = use_condensed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseConsumableItemAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseConsumableItemAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("UseConsumableItemArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        assert (
            len(entities) == 1
        ), "UseConsumableItemArbitrationSystem 期望每次仅处理一个 UseConsumableItemAction 实体"
        await self._request_consumable_arbitration(entities[0])

    #######################################################################################################################################
    async def _request_consumable_arbitration(self, actor_entity: Entity) -> None:

        # 获取当前实体的 UseConsumableItemAction，用于后续的仲裁逻辑
        action = actor_entity.get(UseConsumableItemAction)

        # 获取所有目标实体的当前属性，用于生成仲裁提示信息
        target_stats = collect_target_character_stats(self._game, action.targets)

        # 获取当前回合数，用于生成仲裁提示信息
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 获取当前行动者所在的场景实体，确保后续的仲裁请求能够正确发送到对应的场景
        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, f"无法找到 {actor_entity.name} 所在的场景实体"

        assert stage_entity.has(
            StageDescriptionComponent
        ), "当前场景实体缺少 StageDescriptionComponent 组件！"
        current_stage_description = stage_entity.get(
            StageDescriptionComponent
        ).narrative

        # 生成仲裁提示信息，包括当前行动、目标属性、回合数
        message = build_consumable_arbitration_prompt(
            actor_name=actor_entity.name,
            actor_stats=compute_character_stats(actor_entity),
            item=action.item,
            target_stats=target_stats,
            current_round_number=current_round_number,
            current_stage_description=current_stage_description,
        )

        # 生成精简后的仲裁提示信息，用于在需要时向 LLM 提供更简洁的背景信息
        condensed_message = (
            build_condensed_consumable_arbitration_prompt(
                actor_name=actor_entity.name,
                actor_stats=compute_character_stats(actor_entity),
                item=action.item,
                target_stats=target_stats,
                current_round_number=current_round_number,
                current_stage_description=current_stage_description,
            )
            if self._use_condensed_prompt
            else None
        )

        # 初始化 DeepSeekClient，用于与 LLM 进行交互，并发送仲裁提示信息请求
        chat_client = DeepSeekClient(
            name=stage_entity.name,
            full_prompt=message,
            condensed_prompt=condensed_message,
            messages=self._game.get_agent_memory(stage_entity).messages,
            timeout=60 * 2,
        )

        # 发送仲裁请求给 LLM，并捕获可能的异常，确保整个流程不会因 LLM 请求失败而中断
        try:
            await chat_client.chat()
        except Exception as e:
            logger.error(f"[UseConsumableItemArbitrationSystem] LLM 请求失败: {e}")
            return

        # 检查 LLM 是否返回了有效的消息对象，如果为空则记录错误并返回
        if chat_client.response_ai_message is None:
            logger.error("[UseConsumableItemArbitrationSystem] LLM 回复消息为空")
            return

        # 将 LLM 的仲裁结果应用到游戏中，包括解析 JSON 响应并更新游戏状态
        self._apply_item_arbitration_result(chat_client, actor_entity, action)

    #######################################################################################################################################
    def _apply_item_arbitration_result(
        self,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
        action: UseConsumableItemAction,
    ) -> None:

        if chat_client.response_ai_message is None:
            logger.error("[UseConsumableItemArbitrationSystem] LLM 回复内容为空")
            return

        # 获取当前行动者所在的场景实体，确保后续的仲裁结果能够正确应用到对应的场景
        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert (
            stage_entity is not None
        ), f"UseConsumableItemArbitrationSystem: 无法获取 {actor_entity.name} 所在场景实体！"

        try:

            # 解析 LLM 返回的 JSON 响应，构建 ArbitrationResponse 对象，用于后续的游戏状态更新和广播处理
            response = ArbitrationResponse.model_validate_json(
                extract_json(chat_client.response_content)
            )

            # 验证 final_stats 中的实体是否都存在于游戏中
            for entity_name in response.final_stats:
                if self._game.get_entity_by_name(entity_name) is None:
                    raise ValueError(
                        f"final_stats 中的实体不存在于游戏中: {entity_name}"
                    )

        except Exception as e:
            error_msg = f"消耗品仲裁结果应用失败: {e}"
            logger.error(error_msg)
            return

        # 仲裁者（combat stage）更新自身场景环境快照
        if response.stage_description.strip():
            stage_entity.replace(
                StageDescriptionComponent,
                stage_entity.name,
                response.stage_description,
            )

        # 根据是否使用精简提示，向游戏中添加人类消息，确保 LLM 的请求和响应能够在游戏中被记录和追踪
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

        # assert chat_client.response_ai_message is not None
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=chat_client.response_ai_message,
        )

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=build_consumable_arbitration_broadcast(
                    response.combat_log,
                    response.narrative,
                    current_round_number,
                    action.item.name,
                ),
                stage=stage_entity.name,
                combat_log=response.combat_log,
                narrative=response.narrative,
            ),
            exclude_entities={stage_entity},
        )

        # 遍历仲裁结果中的最终状态，更新每个实体的属性，包括 HP 和状态效果计数器，并向游戏中添加相应的通知消息
        for entity_name, entity_stats in response.final_stats.items():
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

        # 更新本回合的消耗品仲裁日志和计数
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "latest_round 不应为 None"
        latest_round.consumable_combat_log.append(response.combat_log)
        latest_round.consumable_narrative.append(response.narrative)
        latest_round.consumable_use_count += 1
