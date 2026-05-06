"""使用消耗品仲裁系统模块。

响应 UseConsumableItemAction 事件，对消耗品的使用进行 AI 仲裁结算：
计算 HP / 格挡变化，生成战斗日志与演出描述，更新状态效果描述。
不触发 PostArbitrationAction / AddStatusEffectsAction。
"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    UseConsumableItemAction,
    RoundStatsComponent,
    CharacterStats,
    CharacterStatsComponent,
    DeathComponent,
    CombatArbitrationEvent,
    StatusEffectsComponent,
    StatusEffect,
    StatusEffectPhase,
    AddStatusEffectsAction,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class _StatusEffectPatch(BaseModel):
    name: str
    description: str


#######################################################################################################################################
@final
class _EntityFinalStats(BaseModel):
    hp: float
    block: float
    status_effect_patches: List[_StatusEffectPatch] = []


#######################################################################################################################################
@final
class _UseConsumableArbitrationResponse(BaseModel):
    combat_log: str
    final_stats: Dict[str, _EntityFinalStats]
    narrative: str


#######################################################################################################################################
def _generate_consumable_task_hint(
    actor_name: str,
    action: UseConsumableItemAction,
    entity_name: str,
) -> str:
    """生成消耗品仲裁结算后的 AddStatusEffectsAction task_hint。

    与 PlayCardsArbitrationSystem._generate_post_arbitration_task_hint 同语义，
    区分使用者视角与目标视角，供 AddActorStatusEffectsActionSystem 使用。
    """
    item = action.item
    actor_short_name = actor_name.split(".")[-1]
    targets_str = "、".join(t.split(".")[-1] for t in action.targets) or "无"
    effects_line = f"- 潜在词缀：{chr(10).join(item.effects)}" if item.effects else ""
    item_info = f"- 消耗品：{item.name}（{item.description}）" + (
        f"\n{effects_line}" if effects_line else ""
    )

    if entity_name == actor_name:
        return (
            f"消耗品使用结算完成。你本回合使用了：\n"
            f"{item_info}\n"
            f"- 作用目标：{targets_str}\n"
            f"请根据以上使用结果，结合战斗上下文，评估是否追加状态效果。"
        )
    else:
        return (
            f"消耗品使用结算完成。你本回合被 {actor_short_name} 使用消耗品命中：\n"
            f"{item_info}\n"
            f"请根据以上情况，结合战斗上下文，评估是否追加状态效果。"
        )


#######################################################################################################################################
def _generate_defeat_notification() -> str:
    return """# 你的HP已归零，失去战斗能力！"""


#######################################################################################################################################
def _generate_stats_update_notification(final_hp: int, max_hp: int, block: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}
当前格挡: {block}"""


#######################################################################################################################################
def _fmt_duration(duration: int) -> str:
    return "永久" if duration == -1 else f"剩余{duration}回合"


#######################################################################################################################################
def _fmt_effects(effects: List[StatusEffect]) -> str:
    if not effects:
        return "  无"
    return "\n".join(
        f"  - {e.name}（{_fmt_duration(e.duration)}）: {e.description}" for e in effects
    )


#######################################################################################################################################
def _generate_consumable_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    actor_short_name = actor_name.split(".")[-1]
    return f"""# 第 {current_round_number} 回合 · {actor_short_name} 使用消耗品

## 战斗演出

{narrative}

## 数据日志

{combat_log}"""


#######################################################################################################################################
def _generate_consumable_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    actor_block: int,
    action: UseConsumableItemAction,
    target_stats: Dict[str, CharacterStats],
    target_blocks: Dict[str, int],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    target_lines = (
        "\n".join(
            f"- {name}（HP {stats.hp}/{stats.max_hp}，当前格挡 {target_blocks.get(name, 0)}）"
            for name, stats in target_stats.items()
        )
        if target_stats
        else "- 无目标（仅作用于使用者自身）"
    )

    arbitration_effects_lines = (
        f"**使用者 —— {actor_name}**:\n{_fmt_effects(actor_arbitration_effects)}"
    )
    for t_name, t_effects in target_arbitration_effects.items():
        arbitration_effects_lines += (
            f"\n\n**目标 —— {t_name}**:\n{_fmt_effects(t_effects)}"
        )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算（以 JSON 格式返回）

## 使用者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp}，当前格挡 {actor_block}）

## 消耗品

- 名称：{action.item.name}
- 描述：{action.item.description}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 计算规则

根据消耗品描述，推断其对使用者与目标的效果（如恢复 HP、提升格挡、施加增益/减益等）。
仅依据物品描述中明确写明的数值计算；描述模糊时给出合理推断并体现在 narrative 中。
目标 HP = max(0, min(计算后 HP, 最大 HP))
格挡 = max(0, 格挡计算值)
若使用者 HP 已为 0，跳过对其的恢复结算

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "演出描述"
}}
```

### combat_log（简名 = 全名最后一段）

示例：`[英雄|使用治愈药水→自身] HP:英雄 8→13`
多目标示例：`[英雄|使用鼓舞之酒→队友A,队友B] 格挡:队友A +3,队友B +3`

### final_stats

必须包含**使用者与所有目标**，格式：
```json
{{"角色全名": {{"hp": 数值, "block": 数值, "status_effect_patches": []}}}}
```
- hp：0 ≤ hp ≤ 最大 HP
- block：结算后剩余格挡（不低于 0）
- status_effect_patches：仅在本次仲裁**消耗了**某状态效果的 cur 计数时填写，
  格式：`{{"name": "效果名", "description": "更新后的完整描述（含新 cur 值）"}}`
  未被消耗的效果不输出；若无消耗则保持空数组 []

### narrative

60-120 字，第三人称外部视角，纯感官描写，体现消耗品的使用过程与明显效果。"""


#######################################################################################################################################
def _generate_compressed_consumable_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    actor_block: int,
    action: UseConsumableItemAction,
    target_stats: Dict[str, CharacterStats],
    target_blocks: Dict[str, int],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """生成压缩版消耗品仲裁提示词，用于写入对话历史。"""
    target_lines = (
        "\n".join(
            f"- {name}（HP {stats.hp}/{stats.max_hp}，当前格挡 {target_blocks.get(name, 0)}）"
            for name, stats in target_stats.items()
        )
        if target_stats
        else "- 无目标（仅作用于使用者自身）"
    )

    arbitration_effects_lines = (
        f"**使用者 —— {actor_name}**:\n{_fmt_effects(actor_arbitration_effects)}"
    )
    for t_name, t_effects in target_arbitration_effects.items():
        arbitration_effects_lines += (
            f"\n\n**目标 —— {t_name}**:\n{_fmt_effects(t_effects)}"
        )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算（以 JSON 格式返回）

## 使用者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp}，当前格挡 {actor_block}）

## 消耗品

- 名称：{action.item.name}
- 描述：{action.item.description}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}"""


#######################################################################################################################################
@final
class UseConsumableItemArbitrationSystem(ReactiveProcessor):
    """消耗品使用仲裁系统。

    响应 UseConsumableItemAction 事件，调用 LLM 结算消耗品效果（HP/格挡/状态效果描述更新）。
    不触发 PostArbitrationAction 或 AddStatusEffectsAction。
    """

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(UseConsumableItemAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(UseConsumableItemAction) and entity.has(RoundStatsComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # 战斗未进行中则跳过
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("UseConsumableItemArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        for entity in entities:
            stage_entity = self._game.resolve_stage_entity(entity)
            assert (
                stage_entity is not None
            ), f"UseConsumableItemArbitrationSystem: 无法获取 {entity.name} 所在场景实体！"

            logger.debug(
                f"UseConsumableItemArbitrationSystem: [{entity.name}] 触发消耗品仲裁"
            )
            await self._request_consumable_arbitration(stage_entity, entity)

    #######################################################################################################################################
    async def _request_consumable_arbitration(
        self, stage_entity: Entity, actor_entity: Entity
    ) -> None:

        # 获取 UseConsumableItemAction 组件
        action = actor_entity.get(UseConsumableItemAction)

        # 收集目标的当前 HP 与格挡
        target_stats: Dict[str, CharacterStats] = {}
        target_blocks: Dict[str, int] = {}
        for target_name in dict.fromkeys(action.targets):
            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"
            target_stats[target_name] = self._game.compute_character_stats(
                target_entity
            )
            assert target_entity.has(
                RoundStatsComponent
            ), f"目标实体 {target_name} 缺少 RoundStatsComponent！"
            target_blocks[target_name] = target_entity.get(RoundStatsComponent).block

        # 收集使用者当前 HP 与格挡
        actor_block = actor_entity.get(RoundStatsComponent).block
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        # 收集使用者的 arbitration 相位状态效果
        actor_status_comp = actor_entity.get(StatusEffectsComponent)
        actor_arbitration_effects: List[StatusEffect] = [
            e
            for e in (
                actor_status_comp.status_effects
                if actor_status_comp is not None
                else []
            )
            if e.phase == StatusEffectPhase.ARBITRATION
        ]

        # 收集所有目标的 arbitration 相位状态效果
        target_arbitration_effects: Dict[str, List[StatusEffect]] = {}
        for target_name in dict.fromkeys(action.targets):
            t_entity = self._game.get_entity_by_name(target_name)
            assert t_entity is not None, f"无法找到目标实体: {target_name}"
            t_status_comp = t_entity.get(StatusEffectsComponent)
            target_arbitration_effects[target_name] = [
                e
                for e in (
                    t_status_comp.status_effects if t_status_comp is not None else []
                )
                if e.phase == StatusEffectPhase.ARBITRATION
            ]

        actor_stats = self._game.compute_character_stats(actor_entity)

        # 生成仲裁提示词，包含使用者与目标的 HP/格挡、消耗品信息、当前回合数、状态效果等上下文，供 LLM 结算使用
        message = _generate_consumable_arbitration_prompt(
            actor_name=actor_entity.name,
            actor_stats=actor_stats,
            actor_block=actor_block,
            action=action,
            target_stats=target_stats,
            target_blocks=target_blocks,
            current_round_number=current_round_number,
            actor_arbitration_effects=actor_arbitration_effects,
            target_arbitration_effects=target_arbitration_effects,
        )

        # 生成压缩提示词写入对话历史，供 LLM 参考（仅包含关键信息，减少上下文长度）
        compressed_message = (
            _generate_compressed_consumable_arbitration_prompt(
                actor_name=actor_entity.name,
                actor_stats=actor_stats,
                actor_block=actor_block,
                action=action,
                target_stats=target_stats,
                target_blocks=target_blocks,
                current_round_number=current_round_number,
                actor_arbitration_effects=actor_arbitration_effects,
                target_arbitration_effects=target_arbitration_effects,
            )
            if self._use_compressed_prompt
            else None
        )

        # 调用 LLM 进行仲裁结算，获取最终的 HP / 格挡 / 状态效果描述更新结果，以及战斗日志与演出描述
        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=message,
            compressed_prompt=compressed_message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,
        )
        chat_client.chat()

        # 应用仲裁结果：更新 HP / 格挡，回写状态效果描述，广播仲裁日志与演出描述
        self._apply_item_arbitration_result(
            stage_entity, chat_client, actor_entity, action
        )

        # 结算后处理 HP 归零的实体
        self._process_zero_health_entities()

    #######################################################################################################################################
    def _apply_item_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
        action: UseConsumableItemAction,
    ) -> None:
        try:

            # 从 LLM 响应中提取仲裁结果
            response = _UseConsumableArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 验证 final_stats 中的实体是否都存在于游戏中
            for entity_name in response.final_stats:
                if self._game.get_entity_by_name(entity_name) is None:
                    raise ValueError(
                        f"final_stats 中的实体不存在于游戏中: {entity_name}"
                    )

            # 将提示词与响应写入 stage 对话上下文
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

            # 广播消耗品仲裁结果到场景
            current_round_number = len(self._game.current_dungeon.current_rounds or [])
            self._game.broadcast_to_stage(
                entity=stage_entity,
                agent_event=CombatArbitrationEvent(
                    message=_generate_consumable_arbitration_broadcast(
                        response.combat_log,
                        response.narrative,
                        current_round_number,
                        actor_entity.name,
                    ),
                    stage=stage_entity.name,
                    combat_log=response.combat_log,
                    narrative=response.narrative,
                ),
                exclude_entities={stage_entity},
            )

            # 应用 final_stats：更新 HP / 格挡 / 状态效果描述
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
                logger.info(
                    f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}, block: {entity_stats.block}"
                )

                new_block = int(max(0, entity_stats.block))
                round_stats = entity.get(RoundStatsComponent)
                assert (
                    round_stats is not None
                ), f"{entity_name} 缺少 RoundStatsComponent"
                entity.replace(
                    RoundStatsComponent,
                    entity_name,
                    round_stats.energy,
                    new_block,
                )

                # 将 HP / 格挡 更新通知写入对话历史（仅通知受影响的实体）
                self._game.add_human_message(
                    entity=entity,
                    message_content=_generate_stats_update_notification(
                        new_hp, max_hp, new_block
                    ),
                )

                # 回写状态效果描述补丁
                if entity_stats.status_effect_patches:
                    assert entity.has(
                        StatusEffectsComponent
                    ), f"{entity_name} 缺少 StatusEffectsComponent，无法回写状态效果描述"
                    status_comp = entity.get(StatusEffectsComponent)
                    # if status_comp is not None:
                    effect_map = {e.name: e for e in status_comp.status_effects}
                    for patch in entity_stats.status_effect_patches:
                        if patch.name in effect_map:
                            old_desc = effect_map[patch.name].description
                            effect_map[patch.name].description = patch.description
                            logger.info(
                                f"更新 {entity_name} 状态效果「{patch.name}」description: "
                                f"{old_desc!r} → {patch.description!r}"
                            )
                        else:
                            logger.warning(
                                f"status_effect_patches 中的效果「{patch.name}」"
                                f"在 {entity_name} 的 StatusEffectsComponent 中不存在，跳过"
                            )

            # 将仲裁日志写入当前回合
            latest_round = self._game.current_dungeon.latest_round
            assert latest_round is not None, "latest_round 不应为 None"
            latest_round.combat_log.append(response.combat_log)
            latest_round.narrative.append(response.narrative)

            # 消耗品 effects 非空时，为使用者与所有目标触发状态效果评估
            affected_names = list(response.final_stats.keys())
            self._trigger_add_status_effects(actor_entity, action, affected_names)

        except Exception as e:
            logger.error(f"UseConsumableItemArbitrationSystem: 仲裁结算异常: {e}")

    #######################################################################################################################################
    def _process_zero_health_entities(self) -> None:
        """处理生命值归零的实体，为其添加死亡组件。"""
        defeated_entities = self._game.get_group(
            Matcher(all_of=[CharacterStatsComponent], none_of=[DeathComponent])
        ).entities.copy()

        for entity in defeated_entities:
            entity_hp = self._game.compute_character_stats(entity).hp
            if entity_hp <= 0:
                logger.info(f"{entity.name} 已被击败，HP={entity_hp}")
                self._game.add_human_message(entity, _generate_defeat_notification())
                entity.replace(DeathComponent, entity.name)

    #######################################################################################################################################
    def _trigger_add_status_effects(
        self,
        actor_entity: Entity,
        action: UseConsumableItemAction,
        affected_entity_names: List[str],
    ) -> None:
        """消耗品仲裁结算后，为使用者与所有目标添加 AddStatusEffectsAction。

        当 item.effects 为空时跳过，不触发后续 LLM 推理。
        逻辑与 PlayCardsArbitrationSystem._add_status_effects_actions_after_arbitration 对称。
        """
        if not action.item.effects:
            logger.debug(
                f"[{actor_entity.name}] 消耗品 effects 为空，跳过 AddStatusEffectsAction"
            )
            return

        for entity_name in affected_entity_names:
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到实体: {entity_name}"

            task_hint = _generate_consumable_task_hint(
                actor_name=actor_entity.name,
                action=action,
                entity_name=entity_name,
            )
            entity.replace(AddStatusEffectsAction, entity_name, task_hint)
            logger.debug(f"[{entity_name}] 消耗品仲裁后添加 AddStatusEffectsAction")
