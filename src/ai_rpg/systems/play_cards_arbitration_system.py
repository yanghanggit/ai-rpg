"""战斗仲裁动作系统模块。"""

from typing import Dict, Final, List, final
from loguru import logger
from overrides import override
from pydantic import BaseModel
from ..deepseek import DeepSeekClient
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    PlayCardsAction,
    RoundStatsComponent,
    TargetType,
    CharacterStats,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    StatusEffect,
    PhaseType,
    PostArbitrationAction,
    EquippedGearComponent,
    GearItem,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class StatusEffectPatch(BaseModel):
    name: str
    counter: int


#######################################################################################################################################
@final
class EntityFinalStats(BaseModel):
    hp: float
    status_effect_patches: List[StatusEffectPatch] = []


#######################################################################################################################################
@final
class ArbitrationResponse(BaseModel):
    combat_log: str
    final_stats: Dict[str, EntityFinalStats]
    narrative: str
    trigger_post_arbitration: bool = False


#######################################################################################################################################
def _generate_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命値已更新

当前HP: {final_hp}/{max_hp}"""


#######################################################################################################################################
# def _generate_defeat_notification() -> str:
#     return """# 你的HP已归零，失去战斗能力！"""


#######################################################################################################################################
def _generate_post_arbitration_task_hint(
    actor_name: str,
    play_cards_action: PlayCardsAction,
    entity_name: str,
) -> List[str]:
    """生成仲裁结算后的 AddStatusEffectsAction task_hints，区分出牌者视角与目标视角。
    每条 affix 对应一个 hint，公共上下文（卡牌/视角/目标）作为每条 hint 的前缀。

    Args:
        actor_name: 出牌者实体全名
        play_cards_action: 本次出牌的 PlayCardsAction 组件
        entity_name: 当前需要评估状态效果的实体全名

    Returns:
        task_hints 列表，每条对应一个待生成的状态效果
    """
    card = play_cards_action.card
    actor_short_name = actor_name.split(".")[-1]
    targets_str = "、".join(t.split(".")[-1] for t in play_cards_action.targets) or "无"
    action_desc = play_cards_action.action if play_cards_action.action else "（未提供）"

    card_context = (
        f"- 卡牌：{card.name}（{card.description}）\n"
        f"- 单次伤害：{card.damage_dealt}，攻击次数：{card.hit_count}\n"
        + (
            f"- 改变目标行动：{card.energy_delta:+d} 次\n"
            if card.energy_delta != 0
            else ""
        )
        + f"- 行动描述：{action_desc}"
    )

    if entity_name == actor_name:
        header = (
            f"仲裁结算完成。你本回合的出牌信息如下：\n"
            f"{card_context}\n"
            f"- 攻击目标：{targets_str}\n"
            f"请根据以上出牌结果，结合战斗上下文，"
        )
    else:
        header = (
            f"仲裁结算完成。你本回合被命中的信息如下：\n"
            f"- 出牌者：{actor_short_name}\n"
            f"{card_context}\n"
            f"请根据以上受击情况，结合战斗上下文，"
        )

    return [
        f"{header}评估是否追加与以下词缀对应的状态效果：{affix}"
        for affix in card.affixes
    ]


#######################################################################################################################################
def _generate_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    actor_short_name = actor_name.split(".")[-1]
    return f"""# 第 {current_round_number} 回合 · {actor_short_name} 出牌仲裁

## 战斗演出

{narrative}

## 数据日志

{combat_log}"""


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
class _RandomMultiSections:
    """ENEMY_RANDOM_MULTI 专属 prompt 片段"""

    hit_assignment: str
    rules: str
    log_example: str

    def __init__(self, hit_assignment: str, rules: str, log_example: str) -> None:
        self.hit_assignment = hit_assignment
        self.rules = rules
        self.log_example = log_example


#######################################################################################################################################
def _build_random_multi_sections(
    play_cards_action: PlayCardsAction,
) -> _RandomMultiSections:
    """为 ENEMY_RANDOM_MULTI 卡牌构建仲裁 prompt 中的专属片段。

    当 target_type 不是 ENEMY_RANDOM_MULTI 时，所有字段均为空字符串。
    """
    if play_cards_action.card.target_type != TargetType.ENEMY_RANDOM_MULTI:
        return _RandomMultiSections("", "", "")

    hit_lines = "\n".join(
        f"  第{i + 1}击 → {t.split('.')[-1]}"
        for i, t in enumerate(play_cards_action.targets)
    )
    hit_assignment = (
        f"\n## 命中分配（系统预先随机确定，共 {play_cards_action.card.hit_count} 击）\n\n"
        f"{hit_lines}"
    )
    rules = (
        "enemy_random_multi 特殊规则：按「命中分配」逐段结算，每段命中对应目标，"
        "final_stats 须包含出牌者及**所有被命中过的不重复目标**。"
    )
    log_example = "\nrandom_multi 示例：`[英雄|回旋镖→随机:3×3段,敌A×2伤害5,敌B×1伤害3] HP:敌A 15→10 敌B 12→9`"
    return _RandomMultiSections(hit_assignment, rules, log_example)


#######################################################################################################################################
def _generate_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    play_cards_action: PlayCardsAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    actor_gear_modifiers: List[str],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    if target_stats:
        target_line_parts = []
        for name, stats in target_stats.items():
            line = f"- {name}（HP {stats.hp}/{stats.max_hp} | 防御:{stats.defense}）"
            mods = target_gear_modifiers.get(name, [])
            if mods:
                line += "\n  装备修正：" + "、".join(mods)
            target_line_parts.append(line)
        target_lines = "\n".join(target_line_parts)
    else:
        target_lines = "- 无目标"

    arbitration_effects_lines = (
        f"**出牌者 —— {actor_name}**:\n{_fmt_effects(actor_arbitration_effects)}"
    )
    for t_name, t_effects in target_arbitration_effects.items():
        arbitration_effects_lines += (
            f"\n\n**目标 —— {t_name}**:\n{_fmt_effects(t_effects)}"
        )

    action_line = (
        f"- 行动：{play_cards_action.action}"
        if play_cards_action.action
        else "- 行动：（未提供，请根据卡牌描述与战场情境自行演绎）"
    )

    rm = _build_random_multi_sections(play_cards_action)

    modifiers = play_cards_action.card.modifiers
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {a}" for a in modifiers)
        if modifiers
        else ""
    )
    actor_gear_modifiers_line = (
        "\n- 装备即时修正词缀：\n" + "\n".join(f"  - {m}" for m in actor_gear_modifiers)
        if actor_gear_modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）

## 出牌

- 卡牌：{play_cards_action.card.name}
- damage_dealt：{play_cards_action.card.damage_dealt}（单次伤害）
- hit_count：{play_cards_action.card.hit_count}（攻击次数）
{f'- energy_delta：{play_cards_action.card.energy_delta:+d}（改变目标行动次数，已由系统直接结算）' + chr(10) if play_cards_action.card.energy_delta != 0 else ''}{action_line}{modifiers_line}{actor_gear_modifiers_line}{rm.hit_assignment}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 计算规则

单段有效伤害 = max(1, damage_dealt − 目标防御)（最低保底 1；示例：damage_dealt=3, 防御=3 → max(1, 0) = 1；damage_dealt=5, 防御=3 → max(1, 2) = 2）
总伤害 = 各段有效伤害之和（hit_count 次）
目标 HP = max(0, min(当前 HP − 总伤害, 最大 HP))
若 hit_count = 1，按单段正常结算即可
若出牌者 HP 已为 0，跳过结算
仲裁状态效果中的数値修正（额外 hp 扣除、伤害加成等）**叠加**到上述计算规则之上，体现在 final_stats 中。
出牌者防御已提供；当卡牌描述涉及自身减伤/护盾，或仲裁状态效果含反伤规则时，结合上下文决定是否使用。
即时词缀（若有）声明的修正规则**叠加**到上述计算之上，在 final_stats 中体现。
{rm.rules}
## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "战斗演出",
  "trigger_post_arbitration": false
}}
```

### trigger_post_arbitration

布尔值，决定是否触发场景干预系统（stage agent 追加状态效果 / 塞牌）。
判断规则：仅当本回合出牌的 **narrative 叙事中涉及与已存在场景要素的物理交互**（如搅起沙尘、触发机关、破坏地面物件、揭示可借用道具等），且该交互**合理推断可对场内角色产生后续物理影响**时，设为 `true`；
若本回合为纯角色交换（攻击/治疗），无环境互动，输出 `false`。

### combat_log（简名 = 全名最后一段）

正常：`[出牌者简名|卡牌→目标:damage Xx击_count次,伤害Z] HP:目标简名 旧→新`
多段示例：`[英雄|回旋镖→石缝蜥:3x3次,伤害7] HP:石缝蜥 15→8`{rm.log_example}
阵亡跳过：`[出牌者简名|已阵亡，卡牌无法执行]`

### final_stats

必须包含**出牌者与所有目标**，格式：
```json
{{"角色全名": {{"hp": 数值, "status_effect_patches": []}}}}
```
- hp：0 ≤ hp ≤ 最大 HP
- status_effect_patches：仅在本次仲裁改变了某效果的 counter 值时填写，格式：
  `{{"name": "效果名", "counter": <新整数值>}}`
  - name 必须与"仲裁状态效果"中列出的名称完全一致
  - 未改变 counter 的效果不输出；若本次出牌未触发任何 counter 变化，保持空数组 []

### narrative

80-150 字，第三人称外部视角，纯感官描写，无数字/术语/内心。
若本次行动涉及与场景对象的交互（取用、触发、破坏、移动、部分使用等），叙述中须体现该对象在交互后的**物理状态变化**（如"碎石散落殆尽"、"机关齿轮转动一格发出咔哒声"、"绳索断裂后仍有一截悬挂在梁上"），使后续上下文能推断其当前可用性与剩余状态."""


###########################################################################################################################################
def _generate_compressed_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    play_cards_action: PlayCardsAction,
    target_stats: Dict[str, CharacterStats],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
    actor_gear_modifiers: List[str],
    target_gear_modifiers: Dict[str, List[str]],
) -> str:
    """压缩版仲裁提示词，省略静态规则与格式说明，用于写入对话历史减少重复 token。"""
    if target_stats:
        target_line_parts = []
        for name, stats in target_stats.items():
            line = f"- {name}（HP {stats.hp}/{stats.max_hp} | 防御:{stats.defense}）"
            mods = target_gear_modifiers.get(name, [])
            if mods:
                line += "\n  装备修正：" + "、".join(mods)
            target_line_parts.append(line)
        target_lines = "\n".join(target_line_parts)
    else:
        target_lines = "- 无目标"

    arbitration_effects_lines = (
        f"**出牌者 —— {actor_name}**:\n{_fmt_effects(actor_arbitration_effects)}"
    )
    for t_name, t_effects in target_arbitration_effects.items():
        arbitration_effects_lines += (
            f"\n\n**目标 —— {t_name}**:\n{_fmt_effects(t_effects)}"
        )

    action_line = (
        f"- 行动：{play_cards_action.action}"
        if play_cards_action.action
        else "- 行动：（未提供，请根据卡牌描述与战场情境自行演绎）"
    )

    rm = _build_random_multi_sections(play_cards_action)

    modifiers = play_cards_action.card.modifiers
    modifiers_line = (
        "\n- 即时修正词缀：\n" + "\n".join(f"  - {a}" for a in modifiers)
        if modifiers
        else ""
    )
    actor_gear_modifiers_line = (
        "\n- 装备即时修正词缀：\n" + "\n".join(f"  - {m}" for m in actor_gear_modifiers)
        if actor_gear_modifiers
        else ""
    )

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp} | 防御:{actor_stats.defense}）

## 出牌

- 卡牌：{play_cards_action.card.name}
- damage_dealt：{play_cards_action.card.damage_dealt}（单次伤害）
- hit_count：{play_cards_action.card.hit_count}（攻击次数）
{f'- energy_delta：{play_cards_action.card.energy_delta:+d}（改变目标行动次数，已由系统直接结算）' + chr(10) if play_cards_action.card.energy_delta != 0 else ''}{action_line}{modifiers_line}{actor_gear_modifiers_line}{rm.hit_assignment}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}"""


###########################################################################################################################################
def _generate_gear_on_hit_task_hint(
    actor_name: str,
    play_cards_action: PlayCardsAction,
    gear_item: GearItem,
    entity_name: str,
) -> List[str]:
    """生成装备 on_hit_affixes 对应的 AddStatusEffectsAction task_hints（仅目标视角）。"""
    actor_short = actor_name.split(".")[-1]
    card = play_cards_action.card
    header = (
        f"仲裁结算完成。{actor_short} 持有装备「{gear_item.name}」并使用卡牌「{card.name}」命中了你。\n"
        f"请根据以上受击情况，结合战斗上下文，"
    )
    return [
        f"{header}评估是否追加与以下装备词缀对应的状态效果：{affix}"
        for affix in gear_item.on_hit_affixes
    ]


###########################################################################################################################################
@final
class PlayCardsArbitrationSystem(ReactiveProcessor):
    """响应 PlayCardsAction 事件，对单张出牌立即进行 AI 仲裁结算。"""

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
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

        if not self._game.current_dungeon.is_ongoing:
            logger.debug("PlayCardsArbitrationSystem: 战斗未进行中，跳过仲裁")
            return

        for entity in entities:

            stage_entity = self._game.resolve_stage_entity(entity)
            assert stage_entity is not None, f"无法获取 {entity.name} 所在场景实体！"

            logger.debug(f"PlayCardsArbitrationSystem: [{entity.name}] 触发仲裁")
            await self._request_combat_arbitration(stage_entity, entity)

    #######################################################################################################################################
    async def _request_combat_arbitration(
        self, stage_entity: Entity, actor_entity: Entity
    ) -> None:
        """驱动单次出牌的完整仲裁流程。"""
        assert actor_entity.has(
            PlayCardsAction
        ), f"实体 {actor_entity.name} 缺少 PlayCardsAction 组件！"
        play_cards_action = actor_entity.get(PlayCardsAction)

        target_stats: Dict[str, CharacterStats] = {}

        # dict.fromkeys 去重并保序（ENEMY_RANDOM_MULTI 的 targets 长度=hit_count，可能含重复名）
        for target_name in dict.fromkeys(play_cards_action.targets):

            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"

            target_stats[target_name] = self._game.compute_character_stats(
                target_entity
            )

        assert actor_entity.has(
            RoundStatsComponent
        ), f"出牌实体 {actor_entity.name} 缺少 RoundStatsComponent！"
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        actor_arbitration_effects: List[StatusEffect] = (
            self._game.get_status_effects_by_phase(actor_entity, PhaseType.ARBITRATION)
        )

        target_arbitration_effects: Dict[str, List[StatusEffect]] = {}
        for target_name in dict.fromkeys(play_cards_action.targets):
            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"
            target_arbitration_effects[target_name] = (
                self._game.get_status_effects_by_phase(
                    target_entity, PhaseType.ARBITRATION
                )
            )

        actor_gear_modifiers: List[str] = (
            actor_entity.get(EquippedGearComponent).item.modifiers
            if actor_entity.has(EquippedGearComponent)
            else []
        )
        target_gear_modifiers: Dict[str, List[str]] = {}
        for _tgt_name in dict.fromkeys(play_cards_action.targets):
            _tgt_entity = self._game.get_entity_by_name(_tgt_name)
            assert _tgt_entity is not None, f"无法找到目标实体: {_tgt_name}"
            target_gear_modifiers[_tgt_name] = (
                _tgt_entity.get(EquippedGearComponent).item.modifiers
                if _tgt_entity.has(EquippedGearComponent)
                else []
            )

        message = _generate_combat_arbitration_prompt(
            actor_entity.name,
            self._game.compute_character_stats(actor_entity),
            play_cards_action,
            target_stats,
            current_round_number,
            actor_arbitration_effects,
            target_arbitration_effects,
            actor_gear_modifiers,
            target_gear_modifiers,
        )

        compressed_message = (
            _generate_compressed_combat_arbitration_prompt(
                actor_entity.name,
                self._game.compute_character_stats(actor_entity),
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

        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=message,
            compressed_prompt=compressed_message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,
        )
        await chat_client.chat()

        self._apply_arbitration_result(
            stage_entity, chat_client, actor_entity, play_cards_action
        )

        self._game.process_zero_health_entities()

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
        action: PlayCardsAction,
    ) -> None:
        """解析 AI 仲裁响应，更新 HP/状态效果，广播仲裁事件，写入回合记录。解析失败仅记录 error。"""
        try:

            format_response = ArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 验证 final_stats 中的实体名称是否存在于游戏中
            for entity_name, entity_stats in format_response.final_stats.items():
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

            assert (
                chat_client.response_ai_message is not None
            ), "chat_client.response_ai_message 不应为 None"
            self._game.add_ai_message(
                entity=stage_entity,
                ai_message=chat_client.response_ai_message,
            )

            current_round_number = len(self._game.current_dungeon.current_rounds or [])
            self._game.broadcast_to_stage(
                entity=stage_entity,
                agent_event=CombatArbitrationEvent(
                    message=_generate_combat_arbitration_broadcast(
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

            for entity_name, entity_stats in format_response.final_stats.items():

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

                # 回写仲裁阶段状态效果的 counter（更新特殊计数器）
                for patch in entity_stats.status_effect_patches:
                    self._game.apply_status_effect_patch(
                        entity, patch.name, patch.counter
                    )

                self._game.add_human_message(
                    entity=entity,
                    message_content=_generate_stats_update_notification(new_hp, max_hp),
                )

            self._add_status_effects_actions_after_arbitration(
                actor_entity=actor_entity,
                play_cards_action=action,
                affected_entity_names=list(format_response.final_stats.keys()),
            )

            # 确定性结算 energy_delta：直接改变每个目标行动次数（正值增加/负值剥夺），不经 LLM 仲裁
            if action.card.energy_delta != 0:
                for target_name in dict.fromkeys(action.targets):
                    target_entity = self._game.get_entity_by_name(target_name)
                    if target_entity is not None:
                        self._game.give_energy(target_entity, action.card.energy_delta)
                        logger.debug(
                            f"[{target_name}] energy_delta {action.card.energy_delta:+d}"
                        )

            latest_round = self._game.current_dungeon.latest_round
            assert latest_round is not None, "current_rounds 不应为 None"
            latest_round.cards_combat_log.append(format_response.combat_log)
            latest_round.cards_narrative.append(format_response.narrative)

            if format_response.trigger_post_arbitration:
                logger.debug(
                    f"仲裁结果 trigger_post_arbitration=True，触发 PostArbitrationAction"
                )
                stage_entity.replace(
                    PostArbitrationAction, stage_entity.name, actor_entity.name
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _add_status_effects_actions_after_arbitration(
        self,
        actor_entity: Entity,
        play_cards_action: PlayCardsAction,
        affected_entity_names: List[str],
    ) -> None:
        """仲裁结算后为出牌者与所有目标添加 AddStatusEffectsAction。card.affixes 与装备 on_hit_affixes 均为空时跳过。

        Args:
            actor_entity: 出牌者实体
            play_cards_action: 本次出牌的 PlayCardsAction 组件
            affected_entity_names: final_stats 中所有受影响实体的全名列表
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
                task_hints += _generate_post_arbitration_task_hint(
                    actor_name=actor_entity.name,
                    play_cards_action=play_cards_action,
                    entity_name=entity_name,
                )

            # on_hit_affixes 仅作用于命中目标（非出牌者自身）
            if gear_on_hit_affixes and entity_name != actor_entity.name:
                task_hints += _generate_gear_on_hit_task_hint(
                    actor_name=actor_entity.name,
                    play_cards_action=play_cards_action,
                    gear_item=actor_entity.get(EquippedGearComponent).item,
                    entity_name=entity_name,
                )

            if task_hints:
                self._game.accumulate_status_effects_action(entity, task_hints)
                logger.debug(f"[{entity_name}] 仲裁后添加 AddStatusEffectsAction")

    #######################################################################################################################################
