"""使用装备仲裁系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_entity_ops import (
    accumulate_status_effects_action,
    apply_status_effect_patch,
    compute_character_stats,
    get_status_effects_by_phase,
    set_character_hp,
)
from ..game.dbg_combat_processor import process_zero_health_entities
from ..models import (
    UseGearItemAction,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    CharacterStats,
    HumanMessage,
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
        await self._request_gear_arbitration(entities[0])

    #######################################################################################################################################
    async def _request_gear_arbitration(self, actor_entity: Entity) -> None:

        # 获取当前行动者的使用装备动作，用于生成仲裁提示和与 LLM 交互
        action = actor_entity.get(UseGearItemAction)

        # 获取目标实体的状态效果，用于生成仲裁提示和与 LLM 交互
        target_stats: Dict[str, CharacterStats] = {}
        for target_name in dict.fromkeys(action.targets):
            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"
            target_stats[target_name] = compute_character_stats(target_entity)

        # 获取当前回合的回合数，用于生成仲裁提示和与 LLM 交互
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        # 获取目标实体在仲裁阶段的状态效果，用于生成仲裁提示和与 LLM 交互
        target_arbitration_effects: Dict[str, List[StatusEffect]] = {
            target_name: get_status_effects_by_phase(
                self._game.get_entity_by_name(target_name),  # type: ignore[arg-type]
                PhaseType.ARBITRATION,
            )
            for target_name in dict.fromkeys(action.targets)
        }

        # 判断当前行动者是否属于队伍成员，用于生成仲裁提示和与 LLM 交互
        is_party_action = actor_entity.has(PartyMemberComponent)

        # 生成装备仲裁提示消息，包括使用装备动作、目标实体的状态效果、当前回合数等信息
        message = generate_gear_arbitration_prompt(
            action=action,
            target_stats=target_stats,
            current_round_number=current_round_number,
            target_arbitration_effects=target_arbitration_effects,
        )

        # 生成压缩后的装备仲裁提示消息，用于在需要时向 LLM 提供更简洁的上下文信息
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

        # 获取当前行动者所在的场景实体，确保后续的仲裁结果能够正确应用到对应的场景上下文
        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert (
            stage_entity is not None
        ), f"UseGearItemArbitrationSystem: 无法获取 {actor_entity.name} 所在场景实体！"

        # 初始化 DeepSeekClient，用于与 LLM 进行交互，传入生成的装备仲裁提示消息和压缩提示消息（如果启用）
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
            logger.error(f"[UseGearItemArbitrationSystem] LLM 请求失败: {e}")
            return

        if chat_client.response_ai_message is None:
            logger.error("[UseGearItemArbitrationSystem] LLM 返回空响应")
            return

        # 解析 LLM 的响应内容，应用装备仲裁结果，更新游戏状态
        self._apply_gear_arbitration_result(
            chat_client, actor_entity, action, is_party_action
        )

        # 处理血量为零的实体，确保游戏状态的一致性
        process_zero_health_entities(self._game)

    #######################################################################################################################################
    def _apply_gear_arbitration_result(
        self,
        # stage_entity: Entity,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
        action: UseGearItemAction,
        is_party_action: bool,
    ) -> None:

        if chat_client.response_ai_message is None:
            logger.error("[UseGearItemArbitrationSystem] LLM 返回空响应")
            return

        # 获取当前行动者所在的场景实体，确保后续的仲裁结果能够正确应用到对应的场景上下文
        stage_entity = self._game.resolve_stage_entity(actor_entity)
        assert (
            stage_entity is not None
        ), f"UseGearItemArbitrationSystem: 无法获取 {actor_entity.name} 所在场景实体！"

        try:

            # 解析 LLM 返回的 JSON 内容，生成 ArbitrationResponse 对象
            response = ArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 验证 final_stats 中的实体是否都存在于游戏中，确保仲裁结果的有效性
            for entity_name in response.final_stats:
                if self._game.get_entity_by_name(entity_name) is None:
                    raise ValueError(
                        f"final_stats 中的实体不存在于游戏中: {entity_name}"
                    )

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

            # 添加 AI 消息到游戏上下文中，以便后续的仲裁逻辑能够参考 LLM 的响应内容
            self._game.add_ai_message(
                entity=stage_entity,
                ai_message=chat_client.response_ai_message,
            )

            # 广播当前回合的仲裁结果，包括战斗日志和叙事内容，通知场景中的所有实体（除当前场景实体外）
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

            # 更新每个实体的最终状态，包括血量和状态效果，并将这些更新通知到游戏上下文中
            for entity_name, entity_stats in response.final_stats.items():
                entity = self._game.get_entity_by_name(entity_name)
                assert (
                    entity is not None
                ), f"无法找到 final_stats 中的实体: {entity_name}"

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
                        content=stats_update_notification(new_hp, max_hp)
                    ),
                )

                for patch in entity_stats.status_effect_patches:
                    apply_status_effect_patch(entity, patch.name, patch.counter)

            # 将本回合的装备使用战斗日志和叙事内容记录到当前地下城的最新回合中，并增加装备使用计数
            latest_round = self._game.current_dungeon.latest_round
            assert latest_round is not None, "latest_round 不应为 None"
            latest_round.gear_combat_log.append(response.combat_log)
            latest_round.gear_narrative.append(response.narrative)
            latest_round.gear_use_count += 1

            # 触发装备附加状态效果的逻辑，将根据装备的附加属性为目标实体添加相应的状态效果
            self._trigger_add_status_effects(action)

            # 如果仲裁结果指示需要触发后续行动（trigger_post_arbitration=True），则为当前场景实体添加 PostArbitrationAction，以便在下一步逻辑中处理后续行动
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
            accumulate_status_effects_action(entity, task_hints)
            logger.debug(f"[{entity_name}] 装备仲裁后添加 AddStatusEffectsAction")
