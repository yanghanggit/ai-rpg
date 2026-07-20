"""战斗仲裁动作系统模块。"""

from typing import Dict, Final, List, Tuple, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    accumulate_status_effects_action,
    apply_status_effect_patch,
    compute_character_stats,
    get_status_effects_by_phase,
    give_energy,
    set_character_hp,
)
from ..game.dbg_combat_processor import process_zero_health_entities
from ..models import (
    PlayCardsAction,
    RoundStatsComponent,
    CharacterStats,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HumanMessage,
    StatusEffect,
    PhaseType,
    PostArbitrationAction,
    EquippedGearComponent,
)
from ..utils import extract_json_from_code_block
from .arbitration_prompt_builders import (
    ArbitrationResponse,
    generate_combat_arbitration_prompt,
    generate_compressed_combat_arbitration_prompt,
    generate_combat_arbitration_broadcast,
    stats_update_notification,
    generate_play_cards_actor_task_hints,
    generate_play_cards_target_task_hints,
    generate_gear_on_hit_task_hints,
)


###########################################################################################################################################
@final
class PlayCardsArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction 事件，对单张出牌立即进行 AI 仲裁结算。"""

    def __init__(self, game: DBGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

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

        if not self._game.current_combat_room.combat.is_ongoing:
            logger.debug("PlayCardsArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        logger.debug(
            f"PlayCardsArbitrationSystem: 触发仲裁，找到 {len(entities)} 个符合条件的出牌实体"
        )

        for entity in entities:
            await self._request_combat_arbitration(entity)

    #######################################################################################################################################
    async def _request_combat_arbitration(self, actor_entity: Entity) -> None:

        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, f"无法获取 {actor_entity.name} 所在场景实体！"

        """驱动单次出牌的完整仲裁流程。"""
        assert actor_entity.has(
            PlayCardsAction
        ), f"实体 {actor_entity.name} 缺少 PlayCardsAction 组件！"
        play_cards_action = actor_entity.get(PlayCardsAction)

        # dict.fromkeys 去重并保序（ENEMY_SPREAD 的 targets 长度=hit_count，可能含重复名）
        target_stats: Dict[str, CharacterStats] = {}
        for target_name in dict.fromkeys(play_cards_action.targets):
            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"
            target_stats[target_name] = compute_character_stats(target_entity)

        assert actor_entity.has(
            RoundStatsComponent
        ), f"出牌实体 {actor_entity.name} 缺少 RoundStatsComponent！"

        # 获取当前回合数，用于仲裁提示生成
        current_round_number = len(self._game.current_combat_room.combat.rounds or [])

        # 获取出牌实体和目标实体在仲裁阶段的状态效果，用于生成仲裁提示
        actor_arbitration_effects: List[StatusEffect] = get_status_effects_by_phase(
            actor_entity, PhaseType.ARBITRATION
        )

        # 获取目标实体在仲裁阶段的状态效果，用于生成仲裁提示
        target_arbitration_effects: Dict[str, List[StatusEffect]] = {}
        for target_name in dict.fromkeys(play_cards_action.targets):
            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"
            target_arbitration_effects[target_name] = get_status_effects_by_phase(
                target_entity, PhaseType.ARBITRATION
            )

        # 获取出牌实体和目标实体的装备附加属性，用于生成仲裁提示
        actor_gear_modifiers: List[str] = (
            actor_entity.get(EquippedGearComponent).item.modifiers
            if actor_entity.has(EquippedGearComponent)
            else []
        )

        # 获取目标实体的装备附加属性，用于生成仲裁提示
        target_gear_modifiers: Dict[str, List[str]] = {}
        for _tgt_name in dict.fromkeys(play_cards_action.targets):
            _tgt_entity = self._game.get_entity_by_name(_tgt_name)
            assert _tgt_entity is not None, f"无法找到目标实体: {_tgt_name}"
            target_gear_modifiers[_tgt_name] = (
                _tgt_entity.get(EquippedGearComponent).item.modifiers
                if _tgt_entity.has(EquippedGearComponent)
                else []
            )

        # 生成仲裁提示消息，包括出牌实体、目标实体的状态效果和装备附加属性等信息
        message = generate_combat_arbitration_prompt(
            actor_entity.name,
            compute_character_stats(actor_entity),
            play_cards_action,
            target_stats,
            current_round_number,
            actor_arbitration_effects,
            target_arbitration_effects,
            actor_gear_modifiers,
            target_gear_modifiers,
        )

        # 生成压缩后的仲裁提示消息，用于在需要时向 LLM 提供更简洁的上下文信息
        compressed_message = (
            generate_compressed_combat_arbitration_prompt(
                actor_entity.name,
                compute_character_stats(actor_entity),
                play_cards_action,
                target_stats,
                current_round_number,
                actor_arbitration_effects,
                target_arbitration_effects,
                actor_gear_modifiers,
                target_gear_modifiers,
            )
            if self._use_compressed_prompt
            else None
        )

        # [测试] 第 1 回合强制触发场景干预，验证 trigger_post_arbitration=true 完整路径
        # if current_round_number == 1:
        #     self._game.add_human_message(
        #         stage_entity,
        #         "（系统测试指令）本回合为第 1 回合，请将 trigger_post_arbitration 强制设为 true，以验证场景干预系统的完整调用路径。其余字段按实际情况正常推理输出。",
        #     )

        # 初始化 DeepSeekClient，用于与 LLM 进行交互，传入生成的仲裁提示消息和压缩提示消息（如果启用）
        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=message,
            compressed_prompt=compressed_message,
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
        self._apply_arbitration_result(chat_client, actor_entity, play_cards_action)

        # 处理血量为零的实体，触发相应的游戏逻辑，例如移除实体或触发死亡事件
        process_zero_health_entities(self._game)

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
        action: PlayCardsAction,
    ) -> None:
        """解析 AI 仲裁响应，更新 HP/状态效果，广播仲裁事件，写入回合记录。解析失败仅记录 error。"""

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
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(f"Exception: {e}")
            return

        # 验证 final_stats 中的实体名称是否存在于游戏中
        for entity_name, entity_stats in format_response.final_stats.items():
            if self._game.get_entity_by_name(entity_name) is None:
                raise ValueError(f"final_stats 中的实体不存在于游戏中: {entity_name}")

        # 根据是否使用压缩提示，添加上下文。
        if self._use_compressed_prompt:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(
                    content=chat_client.compressed_prompt,
                    combat_arbitration_full_prompt=chat_client.prompt,
                ),
            )
        else:
            self._game.add_human_message(
                entity=stage_entity,
                human_message=HumanMessage(content=chat_client.prompt),
            )

        # 将 AI 的响应消息添加到游戏上下文中，便于后续的回合记录和状态更新。
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=chat_client.response_ai_message,
        )

        # 广播当前回合的仲裁结果，包括战斗日志和叙事内容，通知场景中的所有实体（除当前场景实体外）
        current_round_number = len(self._game.current_combat_room.combat.rounds or [])
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=generate_combat_arbitration_broadcast(
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
        post_arbitration_hp: Dict[str, Tuple[int, int]] = {}
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
            post_arbitration_hp[entity_name] = (new_hp, max_hp)
            logger.info(f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}")

            # 回写仲裁阶段状态效果的 counter（更新特殊计数器）
            for patch in entity_stats.status_effect_patches:
                apply_status_effect_patch(entity, patch.name, patch.counter)

            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=stats_update_notification(new_hp, max_hp)
                ),
            )

        # 根据仲裁后的状态，为出牌者与所有目标添加状态效果动作，确保状态效果在游戏中正确生效。
        self._add_status_effects_actions_after_arbitration(
            actor_entity=actor_entity,
            play_cards_action=action,
            affected_entity_names=list(format_response.final_stats.keys()),
            post_arbitration_hp=post_arbitration_hp,
        )

        # 确定性结算 energy_delta：直接改变每个目标行动次数（正值增加/负值剥夺），不经 LLM 仲裁
        if action.card.energy_delta != 0:
            for target_name in dict.fromkeys(action.targets):
                target_entity = self._game.get_entity_by_name(target_name)
                if target_entity is not None:
                    give_energy(target_entity, action.card.energy_delta)
                    logger.debug(
                        f"[{target_name}] energy_delta {action.card.energy_delta:+d}"
                    )

        # 将本回合的战斗日志和叙事内容添加到当前回合的记录中，便于后续回合的回顾和游戏状态的追踪。
        latest_round = self._game.current_combat_room.combat.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.cards_combat_log.append(format_response.combat_log)
        latest_round.cards_narrative.append(format_response.narrative)

        # 如果仲裁结果触发了后置仲裁动作（trigger_post_arbitration 为 True），则在当前场景实体中添加 PostArbitrationAction，以便在后续阶段执行相应的逻辑。
        if format_response.trigger_post_arbitration:
            logger.debug(
                f"仲裁结果 trigger_post_arbitration=True，触发 PostArbitrationAction"
            )
            stage_entity.replace(
                PostArbitrationAction, stage_entity.name, actor_entity.name
            )

    #######################################################################################################################################
    def _add_status_effects_actions_after_arbitration(
        self,
        actor_entity: Entity,
        play_cards_action: PlayCardsAction,
        affected_entity_names: List[str],
        post_arbitration_hp: Dict[str, Tuple[int, int]],
    ) -> None:
        """仲裁结算后为出牌者与所有目标添加 AddStatusEffectsAction。card.affixes 与装备 on_hit_affixes 均为空时跳过。
        """
        card_affixes = play_cards_action.card.affixes
        has_equipped = actor_entity.has(EquippedGearComponent)
        gear_on_hit_affixes: List[str] = (
            actor_entity.get(EquippedGearComponent).item.on_hit_affixes
            if has_equipped
            else []
        )

        if not card_affixes and not gear_on_hit_affixes:
            logger.debug(
                f"[{actor_entity.name}] 出牌卡牌无延迟词缀且装备无 on_hit_affixes，跳过 AddStatusEffectsAction"
            )
            return

        for entity_name in affected_entity_names:

            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到实体: {entity_name}"

            task_hints: List[str] = []

            if card_affixes:
                if entity_name == actor_entity.name:
                    task_hints += generate_play_cards_actor_task_hints(
                        actor_name=actor_entity.name,
                        play_cards_action=play_cards_action,
                    )
                else:
                    new_hp, max_hp = post_arbitration_hp.get(entity_name, (0, 0))
                    task_hints += generate_play_cards_target_task_hints(
                        actor_name=actor_entity.name,
                        play_cards_action=play_cards_action,
                        new_hp=new_hp,
                        max_hp=max_hp,
                    )

            # on_hit_affixes 仅作用于命中目标（非出牌者自身）
            if gear_on_hit_affixes and entity_name != actor_entity.name:
                new_hp, max_hp = post_arbitration_hp.get(entity_name, (0, 0))
                task_hints += generate_gear_on_hit_task_hints(
                    actor_name=actor_entity.name,
                    play_cards_action=play_cards_action,
                    gear_item=actor_entity.get(EquippedGearComponent).item,
                    new_hp=new_hp,
                    max_hp=max_hp,
                )

            if task_hints:
                accumulate_status_effects_action(entity, task_hints)
                logger.debug(f"[{entity_name}] 仲裁后添加 AddStatusEffectsAction")

    #######################################################################################################################################
