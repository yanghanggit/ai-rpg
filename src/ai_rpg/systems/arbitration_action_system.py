"""战斗仲裁动作系统模块。

响应 PlayCardsAction 事件，对每次单张出牌立即进行 AI 仲裁结算。
每次 pipeline.process() 只有一个角色出牌（ActionCleanupSystem 保证），仲裁随即触发。

核心流程：
1. 从 PlayCardsAction 提取卡牌（name/damage/block/action）与目标列表
2. 解析目标实体的当前 HP，构建仲裁提示词
3. 调用 AI 计算伤害、更新 HP，生成战斗日志与演出描述
4. 遍历 final_hp 更新所有受影响角色（出牌者与目标）的 HP
5. 处理生命值归零的角色，添加死亡组件
"""

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
    CardTargetType,
    CharacterStats,
    CharacterStatsComponent,
    DeathComponent,
    CombatArbitrationEvent,
    StatusEffectsComponent,
    StatusEffect,
    StatusEffectPhase,
    StagePostArbitrationAction,
    AddStatusEffectsAction,
)
from ..utils import extract_json_from_code_block


#######################################################################################################################################
@final
class StatusEffectPatch(BaseModel):
    name: str
    description: str


#######################################################################################################################################
@final
class EntityFinalStats(BaseModel):
    hp: float
    block: float
    status_effect_patches: List[StatusEffectPatch] = []


#######################################################################################################################################
@final
class ArbitrationResponse(BaseModel):
    combat_log: str
    final_stats: Dict[str, EntityFinalStats]
    narrative: str


#######################################################################################################################################
def _generate_stats_update_notification(final_hp: int, max_hp: int, block: int) -> str:
    """生成HP与格挡更新通知消息

    Args:
        final_hp: 更新后的当前HP
        max_hp: 最大HP
        block: 结算后的格挡值

    Returns:
        str: 格式化的属性更新通知消息
    """
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}
当前格挡: {block}"""


#######################################################################################################################################
def _generate_defeat_notification() -> str:
    """生成角色被击败通知消息

    Returns:
        str: 击败通知消息
    """
    return """# 你的HP已归零，失去战斗能力！"""


#######################################################################################################################################
def _generate_post_arbitration_task_hint(
    actor_name: str,
    play_cards_action: PlayCardsAction,
    entity_name: str,
) -> str:
    """生成仲裁结算后的 AddStatusEffectsAction task_hint

    将本次出牌的完整卡牌数据格式化为结构化文本，作为后续状态效果评估的可靠依据，
    避免依赖仲裁 LLM 的压缩输出（combat_log/narrative）导致信息失真。

    Args:
        actor_name: 出牌者实体全名
        play_cards_action: 本次出牌的 PlayCardsAction 组件（包含完整卡牌与目标信息）
        entity_name: 当前需要评估状态效果的实体全名

    Returns:
        结构化的 task_hint 字符串，区分出牌者视角与目标视角
    """
    card = play_cards_action.card
    actor_short_name = actor_name.split(".")[-1]
    targets_str = "、".join(t.split(".")[-1] for t in play_cards_action.targets) or "无"
    action_desc = play_cards_action.action if play_cards_action.action else "（未提供）"

    status_hint_line = (
        f"- 潜在词缀：{chr(10).join(card.effects)}" if card.effects else ""
    )

    card_info = (
        f"- 卡牌：{card.name}（{card.description}）\n"
        f"- 单次伤害：{card.damage_dealt}，攻击次数：{card.hit_count}，格挡增量：{card.block_gain}\n"
        f"- 行动描述：{action_desc}"
        + (f"\n{status_hint_line}" if status_hint_line else "")
    )

    if entity_name == actor_name:
        return (
            f"仲裁结算完成。你本回合的出牌信息如下：\n"
            f"{card_info}\n"
            f"- 攻击目标：{targets_str}\n"
            f"请根据以上出牌结果，结合战斗上下文，评估是否追加状态效果。"
        )
    else:
        return (
            f"仲裁结算完成。你本回合被命中的信息如下：\n"
            f"- 出牌者：{actor_short_name}\n"
            f"{card_info}\n"
            f"请根据以上受击情况，结合战斗上下文，评估是否追加状态效果。"
        )


#######################################################################################################################################
def _generate_combat_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, actor_name: str
) -> str:
    """生成战斗仲裁广播消息。

    Args:
        combat_log: 战斗数据日志
        narrative: 战斗演出描述
        current_round_number: 当前回合数
        actor_name: 出牌角色全名

    Returns:
        格式化的战斗广播消息，包含演出和数据日志
    """
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
    if play_cards_action.card.target_type != CardTargetType.ENEMY_RANDOM_MULTI:
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
        "各目标独立维护剩余格挡；同一目标连续被命中时格挡跨段累计扣减。"
        "final_stats 须包含出牌者及**所有被命中过的不重复目标**。"
    )
    log_example = "\nrandom_multi 示例：`[英雄|回旋镖→随机:3×3段,敌A×2伤害5,敌B×1伤害3] HP:敌A 15→10 敌B 12→9`"
    return _RandomMultiSections(hit_assignment, rules, log_example)


#######################################################################################################################################
def _generate_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    actor_block: int,
    play_cards_action: PlayCardsAction,
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
        else "- 无目标"
    )

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

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp}，当前格挡 {actor_block}）

## 出牌

- 卡牌：{play_cards_action.card.name}
- damage_dealt：{play_cards_action.card.damage_dealt}（单次伤害）
- hit_count：{play_cards_action.card.hit_count}（攻击次数）
- block_gain：{play_cards_action.card.block_gain}
{action_line}{rm.hit_assignment}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}

## 计算规则

**格挡优先消耗**：出牌者先获得 block_gain 格挡（出牌者结算后格挡 = 当前格挡 + block_gain）。
多段攻击逐段结算（hit_count 次）：
  每段实际伤害 = max(0, damage_dealt − 目标当前剩余 block)
  本段 block 消耗量 = min(damage_dealt, 目标当前剩余 block)
  每段命中后，目标 block -= 本段 block 消耗量（block 不低于 0）
  总伤害 = 各段实际伤害之和
目标 HP = max(0, min(当前 HP − 总伤害, 最大 HP))
若 hit_count = 1，按单段正常结算即可
若出牌者 HP 已为 0，跳过结算
仲裁状态效果中的数值修正（额外 hp 扣除、block 加成、伤害加成等）**叠加**到上述计算规则之上，体现在 final_stats 中。
{rm.rules}
## 输出格式

```json
{{
  "combat_log": "字符串",
  "final_stats": {{}},
  "narrative": "战斗演出"
}}
```

### combat_log（简名 = 全名最后一段）

正常：`[出牌者简名|卡牌→目标:damage Xx击_count次,伤害Z] HP:目标简名 旧→新`
多段示例：`[英雄|回旋镖→石缝蜥:3x3次,伤害7] HP:石缝蜥 15→8`{rm.log_example}
阵亡跳过：`[出牌者简名|已阵亡，卡牌无法执行]`

### final_stats

必须包含**出牌者与所有目标**，格式：
```json
{{"角色全名": {{"hp": 数值, "block": 数值, "status_effect_patches": []}}}}
```
- hp：0 ≤ hp ≤ 最大 HP
- block：结算后剩余格挡（出牌者 = 当前格挡 + block_gain；目标 = 当前格挡 − 消耗量，不低于 0）
- status_effect_patches：仅在本次仲裁**消耗了**某状态效果的 cur 计数时填写，格式：
  `{{"name": "效果名", "description": "更新后的完整描述（含新 cur 值，如 cur=1/max=3）"}}`
  - name 必须与"仲裁状态效果"中列出的名称完全一致
  - 未被消耗的效果不输出；cur 耗尽时填 cur=0/max=N（不移除效果，duration 由系统另行维护）
  - 若本次出牌未触发任何 cur 消耗，保持空数组 []

### narrative

80-150 字，第三人称外部视角，纯感官描写，无数字/术语/内心。
若本次行动涉及与场景对象的交互（取用、触发、破坏、移动、部分使用等），叙述中须体现该对象在交互后的**物理状态变化**（如"碎石散落殆尽"、"机关齿轮转动一格发出咔哒声"、"绳索断裂后仍有一截悬挂在梁上"），使后续上下文能推断其当前可用性与剩余状态."""


###########################################################################################################################################
def _generate_compressed_combat_arbitration_prompt(
    actor_name: str,
    actor_stats: CharacterStats,
    actor_block: int,
    play_cards_action: PlayCardsAction,
    target_stats: Dict[str, CharacterStats],
    target_blocks: Dict[str, int],
    current_round_number: int,
    actor_arbitration_effects: List[StatusEffect],
    target_arbitration_effects: Dict[str, List[StatusEffect]],
) -> str:
    """生成战斗结算的压缩版提示词。

    仅包含每次出牌变化的动态感知部分（回合号、出牌者、出牌卡牌、目标状态、仲裁状态效果），
    省略静态的计算规则与输出格式说明，用于写入对话历史以减少重复 token 消耗。
    LLM 推理仍使用 _generate_combat_arbitration_prompt() 生成的完整版。
    """
    target_lines = (
        "\n".join(
            f"- {name}（HP {stats.hp}/{stats.max_hp}，当前格挡 {target_blocks.get(name, 0)}）"
            for name, stats in target_stats.items()
        )
        if target_stats
        else "- 无目标"
    )

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

    return f"""# 第 {current_round_number} 回合：战斗结算（以 JSON 格式返回）

## 出牌者

{actor_name}（HP {actor_stats.hp}/{actor_stats.max_hp}，当前格挡 {actor_block}）

## 出牌

- 卡牌：{play_cards_action.card.name}
- damage_dealt：{play_cards_action.card.damage_dealt}（单次伤害）
- hit_count：{play_cards_action.card.hit_count}（攻击次数）
- block_gain：{play_cards_action.card.block_gain}
{action_line}{rm.hit_assignment}

## 目标

{target_lines}

## 仲裁状态效果

{arbitration_effects_lines}"""


###########################################################################################################################################
@final
class ArbitrationActionSystem(ReactiveProcessor):
    """战斗仲裁系统

    响应每次 PlayCardsAction 事件，立即对该单张出牌进行 AI 仲裁结算。
    每次 pipeline.process() 只有一个角色出牌，仲裁随即触发。
    """

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    #######################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PlayCardsAction) and entity.has(RoundStatsComponent)

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # 仅在战斗进行中时触发（is_ongoing 守卫）
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("ArbitrationActionSystem: 战斗未进行中，跳过仲裁")
            return

        # 开始处理仲裁。
        for entity in entities:

            stage_entity = self._game.resolve_stage_entity(entity)
            assert stage_entity is not None, f"无法获取 {entity.name} 所在场景实体！"

            logger.debug(f"ArbitrationActionSystem: [{entity.name}] 触发仲裁")
            await self._request_combat_arbitration(stage_entity, entity)

    #######################################################################################################################################
    async def _request_combat_arbitration(
        self, stage_entity: Entity, actor_entity: Entity
    ) -> None:
        """驱动单次出牌的完整仲裁流程。

        读取 PlayCardsAction，空卡时走放弃行动分支；否则收集出牌者与目标的
        当前 HP/格挡/仲裁状态效果，构建提示词，调用 AI 结算，最后应用结果并清理死亡实体。
        """
        assert actor_entity.has(
            PlayCardsAction
        ), f"实体 {actor_entity.name} 缺少 PlayCardsAction 组件！"
        play_cards_action = actor_entity.get(PlayCardsAction)
        if play_cards_action.card.name == "":
            # 空卡表示 EnemyPlayDecisionSystem 推理失败，记录放弃行动结果
            logger.warning(
                f"ArbitrationActionSystem: [{actor_entity.name}] 出牌为空卡，执行放弃行动"
            )
            self._apply_forfeit_result(stage_entity, actor_entity)
            return

        # 解析目标实体的当前 HP 与格挡
        target_stats: Dict[str, CharacterStats] = {}
        target_blocks: Dict[str, int] = {}

        # dict.fromkeys 去重并保序（ENEMY_RANDOM_MULTI 的 targets 长度=hit_count，可能含重复名）
        for target_name in dict.fromkeys(play_cards_action.targets):

            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, f"无法找到目标实体: {target_name}"

            target_stats[target_name] = self._game.compute_character_stats(
                target_entity
            )

            assert target_entity.has(
                RoundStatsComponent
            ), f"目标实体 {target_name} 缺少 RoundStatsComponent！"
            target_blocks[target_name] = target_entity.get(RoundStatsComponent).block

        # 解析出牌者的当前 HP 与格挡
        assert actor_entity.has(
            RoundStatsComponent
        ), f"出牌实体 {actor_entity.name} 缺少 RoundStatsComponent！"
        actor_block = actor_entity.get(RoundStatsComponent).block
        current_round_number = len(self._game.current_dungeon.current_rounds or [])

        # 读取出牌者的 arbitration 相位状态效果
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

        # 读取所有目标的 arbitration 相位状态效果
        target_arbitration_effects: Dict[str, List[StatusEffect]] = {}
        for target_name in dict.fromkeys(play_cards_action.targets):
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

        # 构建仲裁提示词
        message = _generate_combat_arbitration_prompt(
            actor_entity.name,
            self._game.compute_character_stats(actor_entity),
            actor_block,
            play_cards_action,
            target_stats,
            target_blocks,
            current_round_number,
            actor_arbitration_effects,
            target_arbitration_effects,
        )

        compressed_message = (
            _generate_compressed_combat_arbitration_prompt(
                actor_entity.name,
                self._game.compute_character_stats(actor_entity),
                actor_block,
                play_cards_action,
                target_stats,
                target_blocks,
                current_round_number,
                actor_arbitration_effects,
                target_arbitration_effects,
            )
            if self._use_compressed_prompt
            else None
        )

        # 输出仲裁提示词日志，包含出牌者、卡牌信息、目标信息和当前回合数
        chat_client = DeepSeekClient(
            name=stage_entity.name,
            prompt=message,
            compressed_prompt=compressed_message,
            context=self._game.get_agent_context(stage_entity).context,
            timeout=60 * 2,
        )
        chat_client.chat()

        # 应用仲裁结果
        self._apply_arbitration_result(
            stage_entity, chat_client, actor_entity, play_cards_action
        )

        # 处理生命值归零的实体，添加死亡组件
        self._process_zero_health_entities()

    #######################################################################################################################################
    def _apply_forfeit_result(self, stage_entity: Entity, actor_entity: Entity) -> None:
        """处理空卡（放弃行动）的默认结算结果。

        当 EnemyPlayDecisionSystem 推理失败保留空卡时，以"放弃行动"作为本次出牌结果，
        补全 combat_log 和 narrative，并广播到场景。
        """
        short_name = actor_entity.name.split(".")[-1]
        combat_log = f"[{short_name}|放弃行动]"
        narrative = f"{short_name}迟疑片刻，最终放弃了这回合的行动。"

        current_round_number = len(self._game.current_dungeon.current_rounds or [])
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=_generate_combat_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    actor_entity.name,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        latest_round = self._game.current_dungeon.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.combat_log.append(combat_log)
        latest_round.narrative.append(narrative)

    #######################################################################################################################################
    def _apply_arbitration_result(
        self,
        stage_entity: Entity,
        chat_client: DeepSeekClient,
        actor_entity: Entity,
        action: PlayCardsAction,
    ) -> None:
        """解析 AI 仲裁响应并将结果写入游戏状态。

        解析 combat_log / final_stats / narrative；更新所有受影响实体的 HP、格挡与
        状态效果 description；广播仲裁事件；触发 AddStatusEffectsAction 与
        StagePostArbitrationAction；将日志追加到当前回合记录。
        解析或校验失败时仅记录 error 日志，不抛出异常。
        """
        try:

            format_response = ArbitrationResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 验证 final_stats 中的实体名称是否存在于游戏中，避免后续更新时找不到实体导致错误
            for entity_name, entity_stats in format_response.final_stats.items():
                if self._game.get_entity_by_name(entity_name) is None:
                    raise ValueError(
                        f"final_stats 中的实体不存在于游戏中: {entity_name}"
                    )

            # 上述能过才能继续执行后续逻辑，确保数据正确性

            # 将仲裁提示词、LLM 原始响应与格式化后的仲裁结果写入角色上下文，供后续查询与调试
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

            # 广播仲裁结果（包含战斗日志与演出描述）到场景
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

            # 遍历 final_stats，更新所有受影响角色（出牌者与目标）的 HP 与格挡, LLM 生成的 final_stats 中必须包含出牌者与所有目标，有可能会有错误！
            for entity_name, entity_stats in format_response.final_stats.items():

                entity = self._game.get_entity_by_name(entity_name)
                assert (
                    entity is not None
                ), f"无法找到 final_stats 中的实体: {entity_name}"

                assert entity.has(
                    CharacterStatsComponent
                ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"

                # 更新 HP
                old_hp = self._game.compute_character_stats(entity).hp
                after_stats = self._game.set_character_hp(entity, int(entity_stats.hp))
                new_hp = after_stats.hp
                max_hp = after_stats.max_hp
                logger.info(
                    f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}, block: {entity_stats.block}"
                )

                # 更新回合动态属性组件中的格挡值（保留 energy/speed 现值）
                new_block = int(max(0, entity_stats.block))
                round_stats = entity.get(RoundStatsComponent)
                assert (
                    round_stats is not None
                ), f"{entity_name} 缺少 RoundStatsComponent"
                entity.replace(
                    RoundStatsComponent,
                    entity_name,
                    round_stats.energy,
                    round_stats.speed,
                    new_block,
                )

                # 回写仲裁阶段状态效果的 description（用于更新 cur 等动态变量）
                if entity_stats.status_effect_patches:
                    status_comp = entity.get(StatusEffectsComponent)
                    if status_comp is not None:
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

                # 将属性更新通知写入角色上下文
                self._game.add_human_message(
                    entity=entity,
                    message_content=_generate_stats_update_notification(
                        new_hp, max_hp, new_block
                    ),
                )

            # 仲裁结算完成后，为出牌者与所有目标添加 AddStatusEffectsAction
            # task_hint 包含本次出牌完整结构化数据，供 AddActorStatusEffectsActionSystem 使用
            self._add_status_effects_actions_after_arbitration(
                actor_entity=actor_entity,
                play_cards_action=action,
                affected_entity_names=list(format_response.final_stats.keys()),
            )

            # 将仲裁结果日志与演出追加到当前回合的 combat_log 和 narrative 中
            latest_round = self._game.current_dungeon.latest_round
            assert latest_round is not None, "current_rounds 不应为 None"
            latest_round.combat_log.append(format_response.combat_log)
            latest_round.narrative.append(format_response.narrative)

            # 仲裁结算成功后，触发 StagePostArbitrationActionSystem
            stage_entity.replace(
                StagePostArbitrationAction, stage_entity.name, actor_entity.name
            )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _process_zero_health_entities(self) -> None:
        """处理生命值归零的实体，为其添加死亡组件。

        遍历所有拥有战斗属性但尚未标记为死亡的实体，
        检查其生命值是否小于等于0。如果是，则:
        1. 记录死亡日志
        2. 向该实体发送被击败通知消息
        3. 为实体添加死亡组件(DeathComponent)
        """
        defeated_entities = self._game.get_group(
            Matcher(all_of=[CharacterStatsComponent], none_of=[DeathComponent])
        ).entities.copy()

        for entity in defeated_entities:
            entity_hp = self._game.compute_character_stats(entity).hp

            # 只有当 HP 小于等于 0 时才处理死亡
            if entity_hp <= 0:
                logger.info(f"{entity.name} 已被击败，HP={entity_hp}")
                self._game.add_human_message(entity, _generate_defeat_notification())
                entity.replace(DeathComponent, entity.name)

    #######################################################################################################################################
    def _add_status_effects_actions_after_arbitration(
        self,
        actor_entity: Entity,
        play_cards_action: PlayCardsAction,
        affected_entity_names: List[str],
    ) -> None:
        """仲裁结算后，为出牌者与所有目标添加 AddStatusEffectsAction。

        task_hint 包含本次出牌的完整结构化数据（卡牌名称、数值、行动描述、目标），
        避免依赖仲裁 LLM 的压缩输出（combat_log/narrative）导致信息失真。
        出牌者与目标的 task_hint 视角不同，便于 LLM 区分身份做出准确判断。

        当 card.effects 为空时，说明该卡牌无持续性副作用，跳过整个流程，
        不触发 AddActorStatusEffectsActionSystem LLM 推理，节省调用。

        若实体缺少 StatusEffectsComponent，先注入空组件以保证
        AddActorStatusEffectsActionSystem 的 filter 能正常通过。

        Args:
            actor_entity: 出牌者实体
            action: 本次出牌的 PlayCardsAction 组件
            affected_entity_names: final_stats 中所有受影响实体的全名列表（出牌者 + 目标）
        """
        # 卡牌无词缀时跳过，不触发后续 LLM 推理
        if not play_cards_action.card.effects:
            logger.debug(
                f"[{actor_entity.name}] 出牌卡牌 effects 为空，跳过 AddStatusEffectsAction"
            )
            return

        for entity_name in affected_entity_names:
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到实体: {entity_name}"

            # 确保实体具有 StatusEffectsComponent，若无则注入空组件
            if not entity.has(StatusEffectsComponent):
                entity.replace(StatusEffectsComponent, entity_name, [])

            # 生成 task_hint，包含本次出牌的完整结构化数据，供 AddActorStatusEffectsActionSystem 使用
            task_hint = _generate_post_arbitration_task_hint(
                actor_name=actor_entity.name,
                play_cards_action=play_cards_action,
                entity_name=entity_name,
            )

            # 为实体添加 AddStatusEffectsAction，task_hint 包含本次出牌的完整结构化数据，供 AddActorStatusEffectsActionSystem 使用
            entity.replace(AddStatusEffectsAction, entity_name, task_hint)
            logger.debug(f"[{entity_name}] 仲裁后添加 AddStatusEffectsAction")

    #######################################################################################################################################
