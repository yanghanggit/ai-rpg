"""使用装备仲裁系统模块。

响应 UseGearItemAction 事件，调用 LLM 结算装备即时修正效果（HP/属性），生成叙事并广播到场景。
stat_bonuses 已由前置动作系统确定性写入 EquippedGearComponent，modifiers 由本系统交 LLM 评估。
"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    UseGearItemAction,
    CharacterStats,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    MonsterComponent,
    PartyMemberComponent,
    StatusEffect,
    PhaseType,
    PostArbitrationAction,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class _GearStatusEffectPatch(BaseModel):
    name: str
    counter: int


#######################################################################################################################################
@final
class _GearEntityFinalStats(BaseModel):
    hp: float
    status_effect_patches: List[_GearStatusEffectPatch] = []


#######################################################################################################################################
@final
class _UseGearArbitrationResponse(BaseModel):
    combat_log: str
    final_stats: Dict[str, _GearEntityFinalStats]
    narrative: str
    trigger_post_arbitration: bool = False


#######################################################################################################################################
def _fmt_stat_bonuses(stats: CharacterStats) -> str:
    return (
        f"HP {stats.hp:+d} | MAX_HP {stats.max_hp:+d} | ATK {stats.attack:+d} | "
        f"DEF {stats.defense:+d} | ENERGY {stats.energy:+d} | SPD {stats.speed:+d}"
    )


#######################################################################################################################################
def _build_target_stats_lines(
    target_stats: Dict[str, CharacterStats],
) -> str:
    """构建目标信息段落：名称、HP。"""
    if not target_stats:
        return "- 无直接目标"
    return "\n".join(
        f"- {name}（HP {stats.hp}/{stats.max_hp}）"
        for name, stats in target_stats.items()
    )


#######################################################################################################################################
def _build_arbitration_effects_lines(
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """构建目标的仲裁状态效果列表。"""
    if not target_arbitration_effects:
        return "无"
    lines_parts = []
    for t_name, t_effects in target_arbitration_effects.items():
        lines_parts.append(f"**{t_name}**:\n{_fmt_effects(t_effects)}")
    return "\n\n".join(lines_parts)


#######################################################################################################################################
def _generate_gear_task_hint(
    action: UseGearItemAction,
    entity: Entity,
) -> List[str]:
    """生成装备仲裁结算后的 AddStatusEffectsAction task_hints，按阵营生成不同视角。"""
    item = action.item
    targets_str = "、".join(action.targets) or "无"
    item_base = (
        f"- 装备：{item.name}（{item.description}）\n"
        f"- 属性加成：{_fmt_stat_bonuses(item.stat_bonuses)}"
    )
    if entity.has(PartyMemberComponent):
        header = (
            f"友方阵营为你装备了「{item.name}」，你受到了作用。\n"
            f"{item_base}\n"
            f"- 作用目标：{targets_str}\n"
            f"请根据以上情况，结合战斗上下文，"
        )
    elif entity.has(MonsterComponent):
        header = (
            f"敌方为你装备了「{item.name}」，你受到了作用。\n"
            f"{item_base}\n"
            f"- 作用目标：{targets_str}\n"
            f"请根据以上情况，结合战斗上下文，"
        )
    else:
        header = (
            f"装备使用结算完成。本回合装备作用情况：\n"
            f"{item_base}\n"
            f"- 作用目标：{targets_str}\n"
            f"请根据以上情况，结合战斗上下文，"
        )
    return [
        f"{header}评估是否追加与以下词缀对应的状态效果：{affix}"
        for affix in item.equip_affixes
    ]


#######################################################################################################################################
def _generate_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


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
def _generate_gear_arbitration_broadcast(
    combat_log: str,
    narrative: str,
    current_round_number: int,
    is_party_action: bool,
    item_name: str,
) -> str:
    """生成装备仲裁广播消息，使用阵营标签。"""
    camp_label = "友方阵营" if is_party_action else "敌方"
    return f"""# 第 {current_round_number} 回合 · {camp_label}使用装备「{item_name}」

## 战斗演出

{narrative}

## 数据日志

{combat_log}"""


#######################################################################################################################################
def _generate_gear_arbitration_prompt(
    action: UseGearItemAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """生成装备仲裁提示词（完整版）。"""
    target_lines = _build_target_stats_lines(target_stats)
    arbitration_effects_lines = _build_arbitration_effects_lines(
        target_arbitration_effects
    )
    item = action.item
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {m}" for m in item.modifiers)
        if item.modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：装备使用结算（以 JSON 格式返回）

## 装备

- 名称：{item.name}
- 描述：{item.description}
- 确定性属性加成（已生效）：{_fmt_stat_bonuses(item.stat_bonuses)}{modifiers_line}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 计算规则

stat_bonuses 所列属性加成已由系统确定性写入，本次仲裁无需重复计算。
仅评估 modifiers（即时修正词缀，若有）对目标 HP 的叠加影响；若无 modifiers，final_stats 中 hp 与当前值一致。
目标 HP = max(0, min(计算后 HP, 最大 HP))

## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "演出描述",
  "trigger_post_arbitration": false
}}
```

### trigger_post_arbitration

布尔值，决定是否触发场景干预系统。
仅当装备行为的 **narrative 叙事中涉及与已存在场景要素的物理交互**（如触发机关、破坏地面物件等），且该交互**合理推断可对场内角色产生后续物理影响**时，设为 `true`；
若为纯属性增益类装备（无环境互动），输出 `false`。

### combat_log（简名 = 全名最后一段）

示例：`[装备寒霜剑→英雄] ATK+3`

### final_stats

必须包含**所有目标**，格式：
```json
{{"角色全名": {{"hp": 数值, "status_effect_patches": []}}}}
```
- hp：0 ≤ hp ≤ 最大 HP
- status_effect_patches：仅在本次仲裁改变了某效果的 counter 值时填写，格式：
  `{{"name": "效果名", "counter": <新整数值>}}`
  - name 必须与"仲裁状态效果"中列出的名称完全一致
  - 未改变 counter 的效果不输出；若未触发任何 counter 变化，保持空数组 []

### narrative

60-120 字，第三人称外部视角，纯感官描写，体现装备更换的瞬间画面与明显效果。"""


#######################################################################################################################################
def _generate_compressed_gear_arbitration_prompt(
    action: UseGearItemAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """生成压缩版装备仲裁提示词，用于写入对话历史。"""
    target_lines = _build_target_stats_lines(target_stats)
    arbitration_effects_lines = _build_arbitration_effects_lines(
        target_arbitration_effects
    )
    item = action.item
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {m}" for m in item.modifiers)
        if item.modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：装备使用结算

## 装备

- 名称：{item.name}
- 描述：{item.description}
- 确定性属性加成（已生效）：{_fmt_stat_bonuses(item.stat_bonuses)}{modifiers_line}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}"""


#######################################################################################################################################
@final
class UseGearItemArbitrationSystem(ReactiveProcessor):
    """响应 UseGearItemAction 事件，LLM 结算装备即时修正效果（HP/属性），生成叙事并广播。"""

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
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

        message = _generate_gear_arbitration_prompt(
            action=action,
            target_stats=target_stats,
            current_round_number=current_round_number,
            target_arbitration_effects=target_arbitration_effects,
        )

        compressed_message = (
            _generate_compressed_gear_arbitration_prompt(
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
            response = _UseGearArbitrationResponse.model_validate_json(
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
                    message=_generate_gear_arbitration_broadcast(
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
                    message_content=_generate_stats_update_notification(new_hp, max_hp),
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

            task_hints = _generate_gear_task_hint(
                action=action,
                entity=entity,
            )
            self._game.accumulate_status_effects_action(entity, task_hints)
            logger.debug(f"[{entity_name}] 装备仲裁后添加 AddStatusEffectsAction")
