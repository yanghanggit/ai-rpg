"""回合结束仲裁系统模块。

仲裁者与出牌仲裁一致：由**所在场景（stage）**担任，结果写入 stage 记忆并全场景广播；
被结算的是发起 pass turn 的行动者（持有者）手牌中带回合结束词缀的卡牌。
"""

import json
from functools import partial
from typing import Dict, Final, List, Optional, final

from loguru import logger
from overrides import override
from pydantic import BaseModel, Field

from ..deepseek import ToolDefinition, ToolFunction, agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_combat_processor import (
    compute_character_hand_block,
    compute_character_stats,
    get_alive_actors_in_stage,
    set_character_hp,
)
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    Card,
    CharacterStatsComponent,
    CombatArbitrationEvent,
    HandComponent,
    HumanMessage,
    MonsterComponent,
    PartyMemberComponent,
    PassTurnAction,
    RoundEntryKind,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_prompt_builders import ArbitrationKind, build_calc_rules_section


###########################################################################################################################################
# 回合结束仲裁提示词构建器
###########################################################################################################################################
@prompt_builder
def _build_turn_end_card_lines(card: Card) -> str:
    """输出一张带回合结束词缀的卡参与仲裁的数据字段。"""
    source = card.source or "未知"
    lines = [
        f"- 卡牌：{card.name}",
        f"- source（来源/注入者）：{source}",
        f"- 叙事（description）：{card.description}",
        f"- damage（单卡单次伤害）：{card.damage}",
        f"- hit_count（单卡攻击次数）：{card.hit_count}",
        f"- block（本卡单牌格挡值）：{card.block}",
        render_labeled_str_list(
            "- 回合结束词缀", card.on_turn_end_affixes, indent="    "
        ),
    ]
    return "\n".join(lines)


def _build_alive_actor_lines(alive_actor_names: List[str]) -> str:
    """构建场上存活角色列表。"""
    return (
        "\n".join(f"- {name}" for name in alive_actor_names)
        if alive_actor_names
        else "- 无存活角色"
    )


def _camp_label(actor: Entity) -> str:
    """返回角色的阵营标签，帮助 LLM 判断「敌人/友方」目标。"""
    if actor.has(PartyMemberComponent):
        return "队伍"
    if actor.has(MonsterComponent):
        return "怪物"
    return "未知阵营"


@prompt_builder
def _build_turn_end_arbitration_tool_prompt(
    holder_name: str,
    cards: List[Card],
    alive_actor_names: List[str],
    current_round_number: int,
) -> str:
    """生成回合结束仲裁提示词（完整版，供 LLM 首轮使用）。"""
    cards_lines = "\n\n".join(_build_turn_end_card_lines(c) for c in cards)
    alive_lines = _build_alive_actor_lines(alive_actor_names)

    return f"""# 第 {current_round_number} 回合：回合结束结算（工具调用模式）

## 回合结束的持有者

{holder_name}

其回合结束（pass turn）时，由你结算以下带回合结束词缀的卡牌的效果。

## 回合结束词缀卡牌

{cards_lines}

## 场上存活角色

{alive_lines}

{build_calc_rules_section(GET_ENTITY_STATS_TOOL.function.name, SET_ENTITY_HP_TOOL.function.name, ArbitrationKind.TURN_END)}

## 回合结束词缀

{holder_name} 是这些卡牌的持有者；每张卡牌的 `source` 是它的来源（生成/注入者名称）；词缀若提及「非 source 者」，指持有者 {holder_name}（当其不等于该卡牌 source 时）。回合结束词缀可能有多条，均为独立规则，须**逐条全部结算**；依各卡牌词缀描述结算，受影响目标由词缀描述与场上存活角色自行判断；持有者自身也可成为目标。不引入词缀未提及的新机制。

## 受击词缀

{GET_ENTITY_STATS_TOOL.function.name} 返回的「受击卡牌」仅列出带受击词缀（on_hit_affixes）的卡牌，用于结算受击效果；它**不是**完整手牌清单，其中展示的 block 为该卡牌自身的单牌格挡值，角色的总格挡以 {GET_ENTITY_STATS_TOOL.function.name} 返回的「总格挡」为准。
受击词缀可能有多条，均为独立规则，须**逐条全部结算**。「受击词缀」仅在**该实体是本次回合结束结算中受到伤害的目标**时触发；持有者自身的受击词缀不触发（除非持有者也同时是本次结算中受到伤害的目标）。依词缀描述结算（如 [反伤] 对造成本次伤害的一方造成伤害），受击词缀的数值以该卡牌在 {GET_ENTITY_STATS_TOOL.function.name} 中返回的 damage 字段为准，不引入词缀未提及的新机制。
受击词缀的结算对象是**造成本次伤害的持有者 {holder_name}**，与目标是否阵亡无关：即使目标在本次结算中被击倒，其受击词缀仍须照常结算，不得因目标已倒而略过。

## 工具使用流程（严格按顺序，逐行推演，不得跳步）

1. **读**：对【持有者 {holder_name}】与【每一个可能受影响的角色】分别调用 {GET_ENTITY_STATS_TOOL.function.name}，拿到各自的 HP / 最大 HP 与总格挡（可在同一次回复中并发调用多个）。
2. **算**：逐张卡、逐条词缀结算——每一条词缀各自写成结算式里的一项，按「计算规则 · 结算」逐行推出每个受影响角色的最终 HP。（这是你自己的推理步骤，务必逐行落笔，不得跳步或心算省略。）
3. **写**：对每个受影响角色（含持有者与所有目标）调用 {SET_ENTITY_HP_TOOL.function.name}，hp 直接填第 2 步算出的最终 HP（可在同一次回复中并发调用多个）。
4. **提交**：调用 {SUBMIT_ARBITRATION_TOOL.function.name} 提交最终结果，结束本次仲裁；combat_log 的每个「旧→新」与「伤害 Z」**逐字抄自上一步 {SET_ENTITY_HP_TOOL.function.name} 的返回**（形如「HP 将更新为 13/15（15 → 13，本次扣减 2）」），不得另行心算或改数；若某条词缀无法按上述计算规则结算，把它原文放进 unsettled_affixes。

## {SUBMIT_ARBITRATION_TOOL.function.name} 字段说明

### combat_log（简名 = 全名最后一段）

示例：`[纸人|回合结束·灼烧→英雄:2伤害] HP:英雄 15→13`

### narrative

60-120 字，第三人称外部视角，纯感官描写，无数字 / 术语 / 内心。
以本次结算所用卡牌的「叙事（description）」为素材，把卡牌意象延展成一段外部可见的动作或现象；不得引入卡牌与其词缀之外的机制。
若卡牌效果改变了某个人或物的状态，描写须体现这一改变，为后续叙事留下可推断的当前状态。"""


@prompt_builder
def _build_turn_end_arbitration_broadcast(
    combat_log: str, narrative: str, current_round_number: int, holder_name: str
) -> str:
    """回合结束仲裁的广播消息生成器（第 N 回合 · <持有者> 回合结束仲裁）。"""
    return f"""# 第 {current_round_number} 回合 · {holder_name} 回合结束仲裁

## 演出

{narrative}

## 数据日志

{combat_log}"""


@prompt_builder
def _build_stats_update_notification(final_hp: int, max_hp: int) -> str:
    return f"""# 你的生命值已更新

当前HP: {final_hp}/{max_hp}"""


###########################################################################################################################################
# 仲裁工具定义（本系统独立定义，与 PlayCardsArbitrationSystem 同名但互不共享）
###########################################################################################################################################
GET_ENTITY_STATS_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="get_entity_stats",
        description="读取指定战斗角色的当前生命值（HP/最大HP）与总格挡（其手牌 block 之和）及其手牌中带受击词缀的卡牌（含这些卡牌的 source/damage/hit_count/block 等数据）。用于获取持有者与目标当前状态。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "角色全名，如 角色.无名 或 怪物.纸俑甲",
                },
            },
            "required": ["entity_name"],
        },
    )
)


SET_ENTITY_HP_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="set_entity_hp",
        description="设置指定战斗角色的当前生命值（自动 clamp 到 0~最大HP）。对每个受影响角色（含持有者与所有目标）都必须调用一次。",
        parameters={
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "角色全名",
                },
                "hp": {
                    "type": "integer",
                    "description": "结算后的新生命值（0 ≤ hp ≤ 最大HP）",
                },
            },
            "required": ["entity_name", "hp"],
        },
    )
)


SUBMIT_ARBITRATION_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name="submit_arbitration",
        description="提交本次回合结束仲裁的最终结果（战斗日志、演出叙事、无法结算的词缀）。调用后本次仲裁结束。",
        parameters={
            "type": "object",
            "properties": {
                "combat_log": {
                    "type": "string",
                    "description": "战斗数据日志",
                },
                "narrative": {
                    "type": "string",
                    "description": "60-120 字第三人称演出叙事",
                },
                "unsettled_affixes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：无法按上述计算规则结算的词缀原文列表（如要求抽牌/回能/额外行动，或凭空叠加没有牌承载的标记），仅供系统统计，不计入结算。",
                },
            },
            "required": ["combat_log", "narrative"],
        },
    )
)


###########################################################################################################################################
# 仲裁工具 handler
###########################################################################################################################################
class _TurnEndArbitrationContext(BaseModel):
    """单个持有者回合结束仲裁的共享结果容器。"""

    hp_changes: Dict[str, int] = Field(default_factory=dict)
    combat_log: Optional[str] = None
    narrative: Optional[str] = None
    unsettled_affixes: List[str] = Field(default_factory=list)


def _collect_hand_on_hit_cards(entity: Entity) -> List[Card]:
    """收集角色手牌中所有带受击词缀的卡牌（持有期间参与受击仲裁）。"""
    hand = entity.get(HandComponent) if entity.has(HandComponent) else None
    if hand is None:
        return []
    return [card for card in hand.cards if card.on_hit_affixes]


def _handle_get_entity_stats(game: DBGGame, entity_name: str) -> str:
    """处理「获取状态工具」调用：返回 HP/总格挡 + 参与受击仲裁的手牌卡牌数据。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"

    stats = compute_character_stats(entity)
    hand_block = compute_character_hand_block(entity)

    # 收集角色手牌中所有带受击词缀的卡牌（持有期间参与受击仲裁）
    hit_cards = _collect_hand_on_hit_cards(entity)
    if hit_cards:
        cards_str = "\n".join(
            f"    - {c.name}（source={c.source or '未知'}, description={c.description}, cost={c.cost}, "
            f"damage={c.damage}, hit_count={c.hit_count}, 单牌 block={c.block}, 受击词缀={c.on_hit_affixes}）"
            for c in hit_cards
        )
    else:
        cards_str = "    - 无"

    return (
        f"【{entity_name}】\n"
        f"- HP：{stats.hp}/{stats.max_hp}\n"
        f"- 总格挡（角色级＝该角色手牌 block 之和；结算伤害时只减这个数）：{hand_block}\n"
        f"- 受击卡牌（仅列出带受击词缀的卡牌，不是完整手牌；下面每张卡的 `单牌 block` 只是它自己那张牌的格挡值，**不是**上面的总格挡）：\n"
        f"{cards_str}"
    )


def _handle_set_entity_hp(
    game: DBGGame, ctx: _TurnEndArbitrationContext, entity_name: str, hp: int
) -> str:
    """处理「写回 HP 工具」调用。"""
    entity = game.get_actor_entity(entity_name)
    if entity is None:
        return f"错误：找不到战斗角色 {entity_name}"
    stats = compute_character_stats(entity)
    clamped = max(0, min(int(hp), stats.max_hp))
    ctx.hp_changes[entity_name] = clamped
    return (
        f"{entity_name} HP 将更新为 {clamped}/{stats.max_hp}"
        f"（{stats.hp} → {clamped}，本次扣减 {stats.hp - clamped}）"
    )


def _handle_submit_arbitration(
    ctx: _TurnEndArbitrationContext,
    combat_log: str,
    narrative: str,
    unsettled_affixes: Optional[List[str]] = None,
) -> str:
    """处理「提交仲裁结果工具」调用。"""
    ctx.combat_log = combat_log
    ctx.narrative = narrative
    if unsettled_affixes:
        ctx.unsettled_affixes = [str(a) for a in unsettled_affixes if str(a).strip()]
    return "仲裁结果已提交"


###########################################################################################################################################
@final
class TurnEndArbitrationSystem(ReactiveProcessor):
    """响应 PassTurnAction，由所在场景（stage）仲裁行动者手牌中的回合结束词缀。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PassTurnAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(PassTurnAction)

    #######################################################################################################################################
    def _collect_hand_turn_end_cards(self, entity: Entity) -> List[Card]:
        """收集角色手牌中所有带回合结束词缀的卡牌（持有期间在回合结束时触发）。"""
        hand = entity.get(HandComponent) if entity.has(HandComponent) else None
        if hand is None:
            return []
        return [card for card in hand.cards if card.on_turn_end_affixes]

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("TurnEndArbitrationSystem: 战斗未进行中，跳过回合结束仲裁")
            return

        if not entities:
            return

        # 以 pass turn 实体定位场景；只处理本次发起 pass turn 的行动者（entities）
        pass_turn_entity = entities[0]
        stage_entity = self._game.resolve_stage_entity(pass_turn_entity)
        assert (
            stage_entity is not None
        ), f"TurnEndArbitrationSystem: 无法找到 {pass_turn_entity.name} 所在的场景实体"

        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )

        # 仅处理本次发起 pass turn 的行动者（PassTurnActionSystem 一次只处理一个）
        turn_end_cards = self._collect_hand_turn_end_cards(pass_turn_entity)
        if not turn_end_cards:
            logger.debug(
                "TurnEndArbitrationSystem: 本次 pass turn 的行动者无回合结束词缀卡牌，跳过"
            )
            return

        # 场上存活角色（含阵营标签，供 LLM 判断目标）
        alive_actors = get_alive_actors_in_stage(self._game, pass_turn_entity)
        alive_actor_names = sorted(
            f"{actor.name}（{_camp_label(actor)}）" for actor in alive_actors
        )

        prompt = _build_turn_end_arbitration_tool_prompt(
            pass_turn_entity.name,
            turn_end_cards,
            alive_actor_names,
            current_round_number,
        )
        ctx = _TurnEndArbitrationContext()

        try:
            ok = await agent_loop(
                name=stage_entity.name,
                prompt=prompt,
                messages=self._game.get_agent_memory(stage_entity).messages,
                tools=[
                    GET_ENTITY_STATS_TOOL,
                    SET_ENTITY_HP_TOOL,
                    SUBMIT_ARBITRATION_TOOL,
                ],
                handlers={
                    GET_ENTITY_STATS_TOOL.function.name: partial(
                        _handle_get_entity_stats, self._game
                    ),
                    SET_ENTITY_HP_TOOL.function.name: partial(
                        _handle_set_entity_hp, self._game, ctx
                    ),
                    SUBMIT_ARBITRATION_TOOL.function.name: partial(
                        _handle_submit_arbitration, ctx
                    ),
                },
                max_rounds=6,
                tool_choice="required",
                terminal_tools=[SUBMIT_ARBITRATION_TOOL],
            )
        except Exception as e:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] agent_loop 异常: {e}"
            )
            return

        if not ok or ctx.combat_log is None or ctx.narrative is None:
            logger.error(
                f"TurnEndArbitrationSystem: [{pass_turn_entity.name}] 回合结束仲裁未正常完成，跳过落库"
            )
            return

        self._apply_turn_end_arbitration_result(
            stage_entity,
            pass_turn_entity,
            ctx,
        )

    #######################################################################################################################################
    def _apply_turn_end_arbitration_result(
        self,
        stage_entity: Entity,
        holder: Entity,
        ctx: _TurnEndArbitrationContext,
    ) -> None:
        """应用单个持有者的回合结束仲裁结果：写场景记忆、更新受影响角色 HP、全场景广播。"""

        assert ctx.combat_log is not None, "combat_log 不应为 None"
        assert ctx.narrative is not None, "narrative 不应为 None"
        combat_log = ctx.combat_log
        narrative = ctx.narrative
        hp_changes = ctx.hp_changes

        # 校验 HP 变更中的实体名称（handler 已校验存在，此处兜底防御）
        for entity_name in hp_changes:
            if self._game.get_entity_by_name(entity_name) is None:
                logger.error(
                    f"TurnEndArbitrationSystem: hp_changes 中的实体不存在于游戏中: {entity_name}"
                )
                return

        # 仲裁者是所在场景（stage），与出牌仲裁一致：结果写入 stage 记忆。
        # agent_loop 已原地写入完整提示词与工具调用轨迹，这里仅补记干净的结构化结果。
        self._game.add_ai_message(
            entity=stage_entity,
            ai_message=AIMessage(
                content=json.dumps(
                    {
                        "combat_log": combat_log,
                        "narrative": narrative,
                        "unsettled_affixes": ctx.unsettled_affixes,
                    },
                    ensure_ascii=False,
                )
            ),
        )

        # 全场景广播（与出牌仲裁一致）：除受影响角色外，持有者与旁观者也需知道回合结束
        # 发生了什么——持有者自身 HP 未必变化（如只伤害对手的词缀）。
        current_round_number = len(
            self._game.current_dungeon_combat_room.combat.rounds or []
        )
        self._game.broadcast_to_stage(
            entity=stage_entity,
            agent_event=CombatArbitrationEvent(
                message=_build_turn_end_arbitration_broadcast(
                    combat_log,
                    narrative,
                    current_round_number,
                    holder.name,
                ),
                stage=stage_entity.name,
                combat_log=combat_log,
                narrative=narrative,
            ),
            exclude_entities={stage_entity},
        )

        # 词缀 telemetry：记录仲裁器无法按计算规则结算的词缀
        for affix in ctx.unsettled_affixes:
            logger.warning(
                f"[TurnEndArbitrationSystem] 词缀无法按计算规则结算（telemetry）: {affix}"
            )

        # 更新每个受影响实体的 HP 状态
        for entity_name, hp in hp_changes.items():
            entity = self._game.get_entity_by_name(entity_name)
            assert entity is not None, f"无法找到 hp_changes 中的实体: {entity_name}"
            assert entity.has(
                CharacterStatsComponent
            ), f"实体 {entity_name} 缺少 CharacterStatsComponent！"

            old_hp = compute_character_stats(entity).hp
            after_stats = set_character_hp(entity, int(hp))
            new_hp = after_stats.hp
            max_hp = after_stats.max_hp
            logger.info(f"更新 {entity_name} HP: {old_hp} → {new_hp}/{max_hp}")

            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=_build_stats_update_notification(new_hp, max_hp)
                ),
            )

        # 将本回合的战斗日志和叙事内容添加到当前回合的记录中
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        assert latest_round is not None, "current_rounds 不应为 None"
        latest_round.record(RoundEntryKind.CARDS, combat_log, narrative)

    #######################################################################################################################################
