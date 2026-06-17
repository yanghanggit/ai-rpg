"""使用消耗品仲裁系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    UseConsumableItemAction,
    CharacterStats,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    EquippedGearComponent,
    MonsterComponent,
    PartyMemberComponent,
    StatusEffect,
    PhaseType,
    PostArbitrationAction,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class _StatusEffectPatch(BaseModel):
    name: str
    counter: int


#######################################################################################################################################
@final
class _EntityFinalStats(BaseModel):
    hp: float
    status_effect_patches: List[_StatusEffectPatch] = []


#######################################################################################################################################
@final
class _UseConsumableArbitrationResponse(BaseModel):
    combat_log: str
    final_stats: Dict[str, _EntityFinalStats]
    narrative: str
    trigger_post_arbitration: bool = False


#######################################################################################################################################
def _build_target_stats_lines(
    target_stats: Dict[str, CharacterStats],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    """构建目标信息段落：名称、HP、装备修正（如有）。"""
    if not target_stats:
        return "- 无直接目标（全场效果或其他特殊情况）"

    target_line_parts = []
    for name, stats in target_stats.items():
        line = f"- {name}（HP {stats.hp}/{stats.max_hp}）"
        mods = target_gear_modifiers.get(name, [])
        if mods:
            line += "\n  装备修正：" + "、".join(mods)
        target_line_parts.append(line)
    return "\n".join(target_line_parts)


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
def _generate_consumable_task_hint(
    action: UseConsumableItemAction,
    entity: Entity,
) -> List[str]:
    """生成消耗品仲裁结算后的 AddStatusEffectsAction task_hints，按阵营生成不同视角。

    每条 affix 对应一个 hint，公共上下文作为前缀。
    """
    item = action.item
    targets_str = "、".join(action.targets) or "无"
    item_base = f"- 消耗品：{item.name}（{item.description}）"

    # 根据实体阵营生成不同视角的 header
    if entity.has(PartyMemberComponent):
        # 友方视角
        header = (
            f"友方阵营使用了消耗品「{item.name}」，你受到了作用。\n"
            f"{item_base}\n"
            f"- 作用目标：{targets_str}\n"
            f"请根据以上情况，结合战斗上下文，"
        )
    elif entity.has(MonsterComponent):
        # 敌方视角
        header = (
            f"敌方使用了消耗品「{item.name}」对你造成影响。\n"
            f"{item_base}\n"
            f"- 作用目标：{targets_str}\n"
            f"请根据以上情况，结合战斗上下文，"
        )
    else:
        # 兜底：未知阵营
        header = (
            f"消耗品使用结算完成。本回合消耗品作用情况：\n"
            f"{item_base}\n"
            f"- 作用目标：{targets_str}\n"
            f"请根据以上情况，结合战斗上下文，"
        )

    return [
        f"{header}评估是否追加与以下词缀对应的状态效果：{affix}"
        for affix in item.affixes
    ]


#######################################################################################################################################
def _generate_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命値已更新

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
def _generate_consumable_arbitration_broadcast(
    combat_log: str,
    narrative: str,
    current_round_number: int,
    is_party_action: bool,
    item_name: str,
) -> str:
    """生成消耗品仲裁广播消息，使用阵营标签。"""
    camp_label = "友方阵营" if is_party_action else "敌方"
    return f"""# 第 {current_round_number} 回合 · {camp_label}使用消耗品「{item_name}」

## 战斗演出

{narrative}

## 数据日志

{combat_log}"""


#######################################################################################################################################
def _generate_consumable_arbitration_prompt(
    action: UseConsumableItemAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    """生成消耗品仲裁提示词（完整版）。"""
    target_lines = _build_target_stats_lines(target_stats, target_gear_modifiers)
    arbitration_effects_lines = _build_arbitration_effects_lines(
        target_arbitration_effects
    )

    modifiers = action.item.modifiers
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {m}" for m in modifiers)
        if modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算（以 JSON 格式返回）

## 消耗品

- 名称：{action.item.name}
- 描述：{action.item.description}{modifiers_line}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 计算规则

根据消耗品描述，推断其对目标的效果（如恢复 HP、施加增益/减益等）。
仅依据物品描述中明确写明的数值计算；描述模糊时给出合理推断并体现在 narrative 中。
目标 HP = max(0, min(计算后 HP, 最大 HP))
即时修正词缀（若有）声明的修正规则叠加到上述计算之上，在 final_stats 中体现。

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
判断规则：仅当本回合消耗品使用的 **narrative 叙事中涉及与已存在场景要素的物理交互**（如搅起沙尘、触发机关、破坏地面物件、揭示可借用道具等），且该交互**合理推断可对场内角色产生后续物理影响**时，设为 `true`；
若本回合为纯恢复/增益类使用（治疗、施加状态效果），无环境互动，输出 `false`。

### combat_log（简名 = 全名最后一段）

示例：`[治愈药水→英雄] HP:英雄 8→13`
多目标示例：`[鼓舞之酒→队友A,队友B] HP:队友A 8→12,队友B 6→10`

### final_stats

必须包含**所有目标**，格式：
```json
{{"角色全名": {{"hp": 数値, "status_effect_patches": []}}}}
```
- hp：0 ≤ hp ≤ 最大 HP
- status_effect_patches：仅在本次仲裁改变了某效果的 counter 值时填写，格式：
  `{{"name": "效果名", "counter": <新整数值>}}`
  - name 必须与"仲裁状态效果"中列出的名称完全一致
  - 未改变 counter 的效果不输出；若本次使用未触发任何 counter 变化，保持空数组 []

### narrative

60-120 字，第三人称外部视角，纯感官描写，体现消耗品的使用过程与明显效果。"""


#######################################################################################################################################
def _generate_compressed_consumable_arbitration_prompt(
    action: UseConsumableItemAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    """生成压缩版消耗品仲裁提示词，用于写入对话历史。"""
    target_lines = _build_target_stats_lines(target_stats, target_gear_modifiers)
    arbitration_effects_lines = _build_arbitration_effects_lines(
        target_arbitration_effects
    )

    modifiers_compressed = action.item.modifiers
    modifiers_line_compressed = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {m}" for m in modifiers_compressed)
        if modifiers_compressed
        else ""
    )

    return f"""# 第 {current_round_number} 回合：消耗品使用结算

## 消耗品

- 名称：{action.item.name}
- 描述：{action.item.description}{modifiers_line_compressed}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}"""


#######################################################################################################################################
@final
class UseConsumableItemArbitrationSystem(ReactiveProcessor):
    """响应 UseConsumableItemAction 事件，调用 LLM 仲裁消耗品效果（HP/状态效果描述更新）。"""

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

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

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("UseConsumableItemArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        assert (
            len(entities) == 1
        ), "UseConsumableItemArbitrationSystem 期望每次仅处理一个 UseConsumableItemAction 实体"

        # for entity in entities:
        entity = entities[0]
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

        action = actor_entity.get(UseConsumableItemAction)

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

        target_gear_modifiers: Dict[str, List[str]] = {}
        for _tgt_name in dict.fromkeys(action.targets):
            _tgt_entity = self._game.get_entity_by_name(_tgt_name)
            assert _tgt_entity is not None, f"无法找到目标实体: {_tgt_name}"
            target_gear_modifiers[_tgt_name] = (
                _tgt_entity.get(EquippedGearComponent).item.modifiers
                if _tgt_entity.has(EquippedGearComponent)
                else []
            )

        # 判断是否为友方阵营行为（用于广播消息）
        is_party_action = actor_entity.has(PartyMemberComponent)

        message = _generate_consumable_arbitration_prompt(
            action=action,
            target_stats=target_stats,
            current_round_number=current_round_number,
            target_arbitration_effects=target_arbitration_effects,
            target_gear_modifiers=target_gear_modifiers,
        )

        compressed_message = (
            _generate_compressed_consumable_arbitration_prompt(
                action=action,
                target_stats=target_stats,
                current_round_number=current_round_number,
                target_arbitration_effects=target_arbitration_effects,
                target_gear_modifiers=target_gear_modifiers,
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

        self._apply_item_arbitration_result(
            stage_entity, chat_client, actor_entity, action, is_party_action
        )

        self._game.process_zero_health_entities()

    #######################################################################################################################################
    def _apply_item_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
        action: UseConsumableItemAction,
        is_party_action: bool,
    ) -> None:
        # 第一步：解析 JSON 响应
        try:
            response = _UseConsumableArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 验证 final_stats 中的实体是否都存在于游戏中
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
                    message=_generate_consumable_arbitration_broadcast(
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

                # 回写状态效果计数器补丁
                for patch in entity_stats.status_effect_patches:
                    self._game.apply_status_effect_patch(
                        entity, patch.name, patch.counter
                    )

            # 更新本回合的消耗品仲裁日志和计数
            latest_round = self._game.current_dungeon.latest_round
            assert latest_round is not None, "latest_round 不应为 None"
            latest_round.consumable_combat_log.append(response.combat_log)
            latest_round.consumable_narrative.append(response.narrative)
            latest_round.consumable_use_count += 1

            # 根据仲裁结果判断是否触发后续场景干预
            self._trigger_add_status_effects(action)

            # 根据 response.trigger_post_arbitration 决定是否触发 PostArbitrationAction
            if response.trigger_post_arbitration:
                logger.debug(
                    f"仲裁结果 trigger_post_arbitration=True，触发 PostArbitrationAction"
                )
                stage_entity.replace(
                    PostArbitrationAction, stage_entity.name, actor_entity.name
                )

        except Exception as e:
            error_msg = f"消耗品仲裁结果应用失败: {e}"
            logger.error(error_msg)

    #######################################################################################################################################
    def _trigger_add_status_effects(
        self,
        action: UseConsumableItemAction,
    ) -> None:
        """消耗品仲裁结算后为所有目标（action.targets）添加 AddStatusEffectsAction。"""
        if not action.item.affixes:
            logger.debug("消耗品 affixes 为空，跳过 AddStatusEffectsAction")
            return

        for entity_name in action.targets:
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到实体: {entity_name}"

            task_hints = _generate_consumable_task_hint(
                action=action,
                entity=entity,
            )
            self._game.accumulate_status_effects_action(entity, task_hints)
            logger.debug(f"[{entity_name}] 消耗品仲裁后添加 AddStatusEffectsAction")
