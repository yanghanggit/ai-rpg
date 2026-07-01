"""使用装备仲裁系统模块。

响应 UseGearItemAction 事件，调用 LLM 结算装备即时修正效果（HP/属性），生成叙事并广播到场景。
stat_bonuses 已由前置动作系统确定性写入 EquippedGearComponent，modifiers 由本系统交 LLM 评估。
"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    UseGearItemAction,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    CharacterStats,
    PartyMemberComponent,
    StatusEffect,
    PhaseType,
    PostArbitrationAction,
)
from ..utils import extract_json_from_code_block
from .arbitration_prompt_builders import (
    ArbitrationResponse,
    generate_gear_arbitration_prompt,
    generate_compressed_gear_arbitration_prompt,
    generate_gear_arbitration_broadcast,
    stats_update_notification,
    generate_gear_equip_task_hints,
)


#######################################################################################################################################
@final
class UseGearItemArbitrationSystem(ReactiveProcessor):
    """响应 UseGearItemAction 事件，LLM 结算装备即时修正效果（HP/属性），生成叙事并广播。"""

    def __init__(self, game: DBGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(UseGearItemAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseGearItemAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("UseGearItemArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        assert (
            len(entities) == 1
        ), "UseGearItemArbitrationSystem 期望每次仅处理一个 UseGearItemAction 实体"

        entity = entities[0]
        stage_entity = self._game.resolve_stage_entity(entity)
        assert (
            stage_entity is not None
        ), f"UseGearItemArbitrationSystem: 无法获取 {entity.name} 所在场景实体！"

        logger.debug(f"UseGearItemArbitrationSystem: [{entity.name}] 触发装备仲裁")
        await self._request_gear_arbitration(stage_entity, entity)

    #######################################################################################################################################
    async def _request_gear_arbitration(
        self, stage_entity: Entity, actor_entity: Entity
    ) -> None:

        action = actor_entity.get(UseGearItemAction)

        target_stats: Dict[str, CharacterStats] = {}
        for target_name in dict.fromkeys(action.targets):
            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"
            target_stats[target_name] = self._game.compute_character_stats(
                target_entity
            )

        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        target_arbitration_effects: Dict[str, List[StatusEffect]] = {
            target_name: self._game.get_status_effects_by_phase(
                self._game.get_entity_by_name(target_name),  # type: ignore[arg-type]
                PhaseType.ARBITRATION,
            )
            for target_name in dict.fromkeys(action.targets)
        }

        is_party_action = actor_entity.has(PartyMemberComponent)

        message = generate_gear_arbitration_prompt(
            action=action,
            target_stats=target_stats,
            current_round_number=current_round_number,
            target_arbitration_effects=target_arbitration_effects,
        )

        compressed_message = (
            generate_compressed_gear_arbitration_prompt(
                action=action,
                target_stats=target_stats,
                current_round_number=current_round_number,
                target_arbitration_effects=target_arbitration_effects,
            )
            if self._use_compressed_prompt
            else None
        )

        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=message,
            compressed_prompt=compressed_message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,
        )
        await chat_client.chat()

        self._apply_gear_arbitration_result(
            stage_entity, chat_client, actor_entity, action, is_party_action
        )

        self._game.process_zero_health_entities()

    #######################################################################################################################################
    def _apply_gear_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
        action: UseGearItemAction,
        is_party_action: bool,
    ) -> None:
        try:
            response = ArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            for entity_name in response.final_stats:
                if self._game.get_entity_by_name(entity_name) is None:
                    raise ValueError(
                        f"final_stats 中的实体不存在于游戏中: {entity_name}"
                    )

            if self._use_compressed_prompt:
                self._game.add_human_message(
                    entity=stage_entity,
                    message_content=chat_client.compressed_prompt,
                    combat_arbitration_full_prompt=chat_client.prompt,
                )
            else:
                self._game.add_human_message(
                    entity=stage_entity,
                    message_content=chat_client.prompt,
                )
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(
                entity=stage_entity,
                ai_message=chat_client.response_ai_message,
            )

            current_round_number = len(self._game.current_dungeon.current_rounds or [])
            self._game.broadcast_to_stage(
                entity=stage_entity,
                agent_event=CombatArbitrationEvent(
                    message=generate_gear_arbitration_broadcast(
                        response.combat_log,
                        response.narrative,
                        current_round_number,
                        is_party_action,
                        action.item.name,
                    ),
                    stage=stage_entity.name,
                    combat_log=response.combat_log,
                    narrative=response.narrative,
                ),
                exclude_entities={stage_entity},
            )

            for entity_name, entity_stats in response.final_stats.items():
                entity = self._game.get_entity_by_name(entity_name)
                assert (
                    entity is not None
                ), f"无法找到 final_stats 中的实体: {entity_name}"

                assert entity.has(
                    CharacterStatsComponent
                ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"

                old_hp = self._game.compute_character_stats(entity).hp
                after_stats = self._game.set_character_hp(entity, int(entity_stats.hp))
                new_hp = after_stats.hp
                max_hp = after_stats.max_hp
                logger.info(f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}")

                self._game.add_human_message(
                    entity=entity,
                    message_content=stats_update_notification(new_hp, max_hp),
                )

                for patch in entity_stats.status_effect_patches:
                    self._game.apply_status_effect_patch(
                        entity, patch.name, patch.counter
                    )

            latest_round = self._game.current_dungeon.latest_round
            assert latest_round is not None, "latest_round 不应为 None"
            latest_round.gear_combat_log.append(response.combat_log)
            latest_round.gear_narrative.append(response.narrative)
            latest_round.gear_use_count += 1

            self._trigger_add_status_effects(action)

            if response.trigger_post_arbitration:
                logger.debug(
                    "仲裁结果 trigger_post_arbitration=True，触发 PostArbitrationAction"
                )
                stage_entity.replace(
                    PostArbitrationAction, stage_entity.name, actor_entity.name
                )

        except Exception as e:
            error_msg = f"装备仲裁结果应用失败: {e}"
            logger.error(error_msg)

    #######################################################################################################################################
    def _trigger_add_status_effects(
        self,
        action: UseGearItemAction,
    ) -> None:
        """装备仲裁结算后为所有目标（action.targets）添加 AddStatusEffectsAction。"""
        if not action.item.equip_affixes:
            logger.debug("装备 equip_affixes 为空，跳过 AddStatusEffectsAction")
            return

        for entity_name in action.targets:
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到实体: {entity_name}"

            task_hints = generate_gear_equip_task_hints(
                action=action,
                entity=entity,
            )
            self._game.accumulate_status_effects_action(entity, task_hints)
            logger.debug(f"[{entity_name}] 装备仲裁后添加 AddStatusEffectsAction")
