"""卡牌运转系统：牌被打出并结算完毕后，由牌的主人自己让它在牌堆里继续运转。

打出来造成什么由场景仲裁；牌之后在牌堆里怎么活由持有者自己决定——复制、移动、改写字段。
结算者就是持有者本人（不是场景），结果只写他自己的记忆：牌是私产，不广播。
"""

import re
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Dict, Final, List, Optional, Tuple, final
from uuid import uuid4

from loguru import logger
from overrides import override

from ..deepseek import agent_loop
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..llm import ToolDefinition, ToolFunction
from ..models import (
    ActorComponent,
    Card,
    DeckComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    HandComponent,
    PlayCardsAction,
    apply_numeric_design,
    render_labeled_str_list,
)
from ..utils import prompt_builder
from .arbitration_common import (
    RoundKind,
    compress_loop_to_summary,
    make_loop_id,
    record_aborted_loop,
)
from .card_pile_common import (
    PILE_DECK,
    PILE_DISCARD,
    PILE_DRAW,
    PILE_EXHAUST,
    PILE_HAND,
    PILE_LABELS,
    Pile,
    record_pile_change,
)

#########################################################################################################################################
# 结算上限：给 LLM 自由度的同时守住"不会把记忆/存档撑爆"的硬边界
#########################################################################################################################################
MAX_NEW_CARDS_PER_RESOLUTION: Final[int] = 1  # 单次结算最多新造几张牌
PILE_CAP_FACTOR: Final[int] = 2  # 单个容器容量 = 牌库张数 × 该系数
REF_PREFIX_LEN: Final[int] = 8  # 卡牌引用 = uuid 前 N 位（副本 uuid 全新，前缀不撞）
_UUID_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{6,}")

PILES: Final[Tuple[str, ...]] = (
    PILE_HAND,
    PILE_DRAW,
    PILE_DISCARD,
    PILE_EXHAUST,
    PILE_DECK,
)
WRITABLE_PILES: Final[Tuple[str, ...]] = (
    PILE_HAND,
    PILE_DRAW,
    PILE_DISCARD,
    PILE_EXHAUST,
)


#########################################################################################################################################
def _pile_cards(entity: Entity, pile: str) -> List[Card]:
    """取某个容器里的牌列表（只读快照；写入请用 `_write_pile`）。"""
    match pile:
        case Pile.HAND:
            assert entity.has(HandComponent), f"{entity.name} 缺少 HandComponent"
            return entity.get(HandComponent).cards
        case Pile.DRAW:
            assert entity.has(
                DrawPileComponent
            ), f"{entity.name} 缺少 DrawPileComponent"
            return entity.get(DrawPileComponent).cards
        case Pile.DISCARD:
            assert entity.has(
                DiscardPileComponent
            ), f"{entity.name} 缺少 DiscardPileComponent"
            return entity.get(DiscardPileComponent).cards
        case Pile.EXHAUST:
            assert entity.has(
                ExhaustPileComponent
            ), f"{entity.name} 缺少 ExhaustPileComponent"
            return entity.get(ExhaustPileComponent).cards
        case Pile.DECK:
            assert entity.has(DeckComponent), f"{entity.name} 缺少 DeckComponent"
            return entity.get(DeckComponent).cards
        case _:
            raise AssertionError(f"未知容器 {pile!r}")


def _write_pile(entity: Entity, pile: str, cards: List[Card]) -> None:
    """把某个容器整体写回——容器数据的唯一写入口是 `Entity.replace`。"""
    match pile:
        case Pile.HAND:
            entity.replace(HandComponent, entity.name, cards)
        case Pile.DRAW:
            draw_pile = entity.get(DrawPileComponent)
            entity.replace(
                DrawPileComponent, entity.name, cards, draw_pile.retained_cards
            )
        case Pile.DISCARD:
            entity.replace(DiscardPileComponent, entity.name, cards)
        case Pile.EXHAUST:
            entity.replace(ExhaustPileComponent, entity.name, cards)
        case Pile.DECK:
            entity.replace(DeckComponent, entity.name, cards)
        case _:
            raise AssertionError(f"未知容器 {pile!r}")


def _pile_label(pile: str) -> str:
    return PILE_LABELS[pile]


def _ref(card: Card) -> str:
    return card.uuid[:REF_PREFIX_LEN]


def _card_line(card: Card) -> str:
    """列表项：引用 + 名称 + 参与运转的数值 + 词缀条数。"""
    affixes = len(card.on_play_affixes) + len(card.engine_affixes)
    return f"{_ref(card)}  「{card.name}」（cost {card.cost} / damage {card.damage} / hits {card.hit_count} / block {card.block} / 词缀 {affixes} 条）"


def _pile_cap(entity: Entity) -> int:
    """单个容器的容量上限：牌库张数 × 系数（牌库是这套牌的"总量"参照）。"""
    return max(len(_pile_cards(entity, PILE_DECK)), 1) * PILE_CAP_FACTOR


def _find_card(entity: Entity, ref: str) -> Tuple[str, Card]:
    """按引用定位一张可写的牌：认 uuid 前缀，也容忍模型把整行（含容器名 / 牌名）抄进来。

    牌库不参与解析：战斗中的牌是牌库副本、uuid 与牌库原牌相同，把只读的牌库算进来会撞引用。
    """
    token = _UUID_TOKEN_RE.search(ref.strip().lower())
    matches = [
        (pile, card)
        for pile in WRITABLE_PILES
        for card in _pile_cards(entity, pile)
        if token is not None and card.uuid.startswith(token.group())
    ]
    if not matches:
        # 退化路径：模型直接给了牌名，且这个名字在自己可写的牌堆里唯一
        name = ref.strip()
        matches = [
            (pile, card)
            for pile in WRITABLE_PILES
            for card in _pile_cards(entity, pile)
            if card.name == name
        ]
    assert (
        len(matches) == 1
    ), f"卡牌引用 {ref!r} 命中 {len(matches)} 张。引用只填 uuid 前 {REF_PREFIX_LEN} 位（如 f65a7a4c），不要带容器名或牌名；可用 {LIST_PILES_TOOL_NAME} 重新确认"
    return matches[0]


#########################################################################################################################################
@dataclass
class OperationContext:
    """一次运转结算的运行状态：做了什么、造了几张牌、模型自己的总结。"""

    owner_name: str
    played_card_name: str
    created: int = 0
    actions: List[str] = field(default_factory=list)
    unresolved: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    finished: bool = False


#########################################################################################################################################
# 工具 handler
#########################################################################################################################################
def _handle_list_piles(entity: Entity, ctx: OperationContext) -> str:
    """列出自己全部容器的内容与容量。"""
    blocks: List[str] = []
    cap = _pile_cap(entity)
    for pile in PILES:
        cards = _pile_cards(entity, pile)
        read_only = "（只读）" if pile not in WRITABLE_PILES else ""
        lines = "\n".join(f"  - {_card_line(card)}" for card in cards) or "  （空）"
        blocks.append(
            f"{_pile_label(pile)}{read_only}：{len(cards)} 张 / 上限 {cap}\n{lines}"
        )
    return "\n\n".join(blocks)


def _handle_copy_card(
    entity: Entity,
    ctx: OperationContext,
    source_ref: str,
    to_pile: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    cost: Optional[int] = None,
    damage: Optional[int] = None,
    hit_count: Optional[int] = None,
    block: Optional[int] = None,
) -> str:
    """把一张牌复制一份到指定容器；副本 uuid 全新，可顺带改写副本字段。"""
    if to_pile not in WRITABLE_PILES:
        return f"错误：{to_pile!r} 不可写入（可选：{', '.join(WRITABLE_PILES)}）"
    if ctx.created >= MAX_NEW_CARDS_PER_RESOLUTION:
        return f"错误：本次结算最多新造 {MAX_NEW_CARDS_PER_RESOLUTION} 张牌，额度已用完；若确需更多，请写进 unresolved 说明缘由"

    source_pile, source = _find_card(entity, source_ref)
    target = _pile_cards(entity, to_pile)
    if len(target) + 1 > _pile_cap(entity):
        return f"错误：{_pile_label(to_pile)} 已达容量上限 {_pile_cap(entity)} 张"

    copied = source.model_copy(deep=True)
    copied.uuid = str(uuid4())
    apply_numeric_design(
        copied, cost=cost, damage=damage, hit_count=hit_count, block=block
    )
    if name is not None:
        copied.name = name
    if description is not None:
        copied.description = description

    new_target = [*target, copied]
    _write_pile(entity, to_pile, new_target)
    ctx.created += 1
    ctx.actions.append(
        f"复制「{source.name}」（{_pile_label(source_pile)}）→ {_pile_label(to_pile)}「{copied.name}」"
    )
    return f"已复制：{_pile_label(to_pile)}新增「{copied.name}」（引用 {_ref(copied)}；{_pile_label(to_pile)}现有 {len(new_target)} 张）"


def _handle_move_card(
    entity: Entity,
    ctx: OperationContext,
    card_ref: str,
    to_pile: str,
    at_top: bool = False,
) -> str:
    """在自己容器之间移动一张牌（`at_top=true` 时放到目标容器最前）。"""
    if to_pile not in WRITABLE_PILES:
        return f"错误：{to_pile!r} 不可写入（可选：{', '.join(WRITABLE_PILES)}）"

    source_pile, card = _find_card(entity, card_ref)
    if source_pile == to_pile:
        return f"错误：「{card.name}」已经在{_pile_label(to_pile)}里"

    new_source = [c for c in _pile_cards(entity, source_pile) if c is not card]
    target_cards = _pile_cards(entity, to_pile)
    new_target = [card, *target_cards] if at_top else [*target_cards, card]
    _write_pile(entity, source_pile, new_source)
    _write_pile(entity, to_pile, new_target)

    ctx.actions.append(
        f"移动「{card.name}」：{_pile_label(source_pile)} → {_pile_label(to_pile)}"
    )
    return f"已移动：「{card.name}」现在在{_pile_label(to_pile)}（{_pile_label(to_pile)}现有 {len(new_target)} 张）"


def _handle_modify_card(
    entity: Entity,
    ctx: OperationContext,
    card_ref: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    cost: Optional[int] = None,
    damage: Optional[int] = None,
    hit_count: Optional[int] = None,
    block: Optional[int] = None,
    playable: Optional[bool] = None,
    exhaust: Optional[bool] = None,
    retain: Optional[bool] = None,
    ethereal: Optional[bool] = None,
    transferable: Optional[bool] = None,
) -> str:
    """改写一张牌自身的字段（名称 / 叙事 / 数值 / 布尔标志）。"""
    pile, card = _find_card(entity, card_ref)
    changed: List[str] = []

    before = card.model_dump()
    updated = card.model_copy(deep=True)
    apply_numeric_design(
        updated, cost=cost, damage=damage, hit_count=hit_count, block=block
    )
    for attr, value in (
        ("name", name),
        ("description", description),
        ("playable", playable),
        ("exhaust", exhaust),
        ("retain", retain),
        ("ethereal", ethereal),
        ("transferable", transferable),
    ):
        if value is not None:
            setattr(updated, attr, value)

    for attr, value in updated.model_dump().items():
        if before[attr] != value:
            changed.append(f"{attr}: {before[attr]!r} → {value!r}")

    assert changed, f"modify_card 没有实际改动「{updated.name}」"
    cards = _pile_cards(entity, pile)
    _write_pile(
        entity,
        pile,
        [updated if existing is card else existing for existing in cards],
    )
    ctx.actions.append(
        f"改写{_pile_label(pile)}的「{card.name}」：{'；'.join(changed)}"
    )
    return f"已改写「{card.name}」：{'；'.join(changed)}"


def _handle_submit_card_operation(
    ctx: OperationContext,
    summary: str,
    unresolved: Optional[List[str]] = None,
) -> str:
    """提交结算：模型自己的总结 + 未能完成的词缀。"""
    ctx.summary = summary
    ctx.unresolved = list(unresolved or [])
    ctx.finished = True
    return "已提交，本次运转结算结束。"


#########################################################################################################################################
# 工具定义
#########################################################################################################################################
LIST_PILES_TOOL_NAME: Final[str] = "list_piles"
COPY_CARD_TOOL_NAME: Final[str] = "copy_card"
MOVE_CARD_TOOL_NAME: Final[str] = "move_card"
MODIFY_CARD_TOOL_NAME: Final[str] = "modify_card"
SUBMIT_OPERATION_TOOL_NAME: Final[str] = "submit_card_operation"

_PILE_ARG_SCHEMA: Final[Dict[str, Any]] = {
    "type": "string",
    "enum": list(WRITABLE_PILES),
    "description": "目标容器："
    + "、".join(f"{p}={_pile_label(p)}" for p in WRITABLE_PILES),
}

_CARD_FIELD_PROPS: Final[Dict[str, Any]] = {
    "name": {"type": "string", "description": "可选：新的卡牌名"},
    "description": {"type": "string", "description": "可选：新的叙事描述（不含数值）"},
    "cost": {"type": "integer", "description": "可选：新的 cost"},
    "damage": {"type": "integer", "description": "可选：新的 damage"},
    "hit_count": {"type": "integer", "description": "可选：新的 hit_count"},
    "block": {"type": "integer", "description": "可选：新的 block"},
}

LIST_PILES_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name=LIST_PILES_TOOL_NAME,
        description="列出你自己全部容器（手牌 / 抽牌堆 / 弃牌堆 / 消耗堆 / 牌库）里的牌及其引用、数值、词缀条数与容量上限。牌库只读。",
        parameters={"type": "object", "properties": {}},
    )
)

COPY_CARD_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name=COPY_CARD_TOOL_NAME,
        description=(
            f"复制一张你自己的牌到指定容器（副本 uuid 全新、词缀原样保留），可顺带改写副本的字段。单次结算最多新造 {MAX_NEW_CARDS_PER_RESOLUTION} 张，容器不得超过容量上限。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "source_ref": {
                    "type": "string",
                    "description": "被复制的牌引用：只填 uuid 前 8 位（如 f65a7a4c），不要带容器名或牌名",
                },
                "to_pile": _PILE_ARG_SCHEMA,
                **_CARD_FIELD_PROPS,
            },
            "required": ["source_ref", "to_pile"],
        },
    )
)

MOVE_CARD_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name=MOVE_CARD_TOOL_NAME,
        description="在你自己的容器之间移动一张牌；`at_top=true` 放到目标容器最前（如放回抽牌堆顶）。",
        parameters={
            "type": "object",
            "properties": {
                "card_ref": {
                    "type": "string",
                    "description": "要移动的牌引用：只填 uuid 前 8 位，不要带容器名或牌名",
                },
                "to_pile": _PILE_ARG_SCHEMA,
                "at_top": {
                    "type": "boolean",
                    "description": "可选：true=放到目标容器最前，false/省略=追加到最后",
                },
            },
            "required": ["card_ref", "to_pile"],
        },
    )
)

MODIFY_CARD_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name=MODIFY_CARD_TOOL_NAME,
        description=(
            "改写一张你自己的牌自身的字段（名称 / 叙事 / 数值 / 布尔标志）。只改你提交的字段，其余保持不变；至少要有字段真的发生变化。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "card_ref": {
                    "type": "string",
                    "description": "要改写的牌引用：只填 uuid 前 8 位，不要带容器名或牌名",
                },
                **_CARD_FIELD_PROPS,
                "playable": {"type": "boolean", "description": "可选：是否可出牌"},
                "exhaust": {
                    "type": "boolean",
                    "description": "可选：出牌后是否进消耗堆",
                },
                "retain": {"type": "boolean", "description": "可选：回合末是否保留"},
                "ethereal": {
                    "type": "boolean",
                    "description": "可选：pass turn 时是否消散",
                },
                "transferable": {"type": "boolean", "description": "可选：是否可传递"},
            },
            "required": ["card_ref"],
        },
    )
)

SUBMIT_OPERATION_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name=SUBMIT_OPERATION_TOOL_NAME,
        description="提交本次运转结算：你做了什么（第一人称总结）+ 没能完成的词缀（若有）。调用后本次结算结束。",
        parameters={
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "第一人称总结：这次运转发生了什么（不含工具调用细节，写清结果）",
                },
                "unresolved": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选：未能完成或超出上限的词缀及原因",
                },
            },
            "required": ["summary"],
        },
    )
)


#########################################################################################################################################
@prompt_builder
def build_operation_prompt(
    owner_name: str,
    card: Card,
    pile_block: str,
    round_number: int,
) -> str:
    """运转结算的提示词：这张牌在哪、要做什么、能做到什么。"""
    return f"""# 第 {round_number} 回合：你的牌在运转

你是 {owner_name}。你刚打出了「{card.name}」，它现在已经离开手牌（在弃牌堆或消耗堆里）。
「{card.name}」的叙事：{card.description}

## 运转型词缀（共 {len(card.engine_affixes)} 条，逐条结算，一条都不能漏）

{render_labeled_str_list("- 运转型词缀", card.engine_affixes, indent="    ")}

这条词缀不造成伤害、不改变 HP——它决定这张牌在牌堆里如何继续存在：复制、移动、被改写成别的样子。
词缀文本是命令，工具是手段：怎么实现由你判断，但不得超出词缀文本允许的范围。

## 你的牌堆

{pile_block}

## 结算规则

- 只能操作**你自己**的容器；牌库（deck）只读，不能写入。
- 本次结算最多新造 {MAX_NEW_CARDS_PER_RESOLUTION} 张牌；单个容器不得超过容量上限（牌库张数 × {PILE_CAP_FACTOR}）。
- 复制体保留原词缀（这是它继续运转的前提）；数值 / 名称 / 叙事 / 布尔标志可改。
- 词缀文本本身不在这里改写——它是这张牌的设计，不属于运转。
- 做不到、或超出上限的部分写进 `unresolved`，不要假装做了。

## 工具流程

1. `{LIST_PILES_TOOL_NAME}`：确认这张牌现在在哪个容器。每个列表项的**第一个字段就是引用**（如 `f65a7a4c`），工具里只填这 8 位，不要带容器名或牌名。
2. 按词缀逐条执行：`{COPY_CARD_TOOL_NAME}` / `{MOVE_CARD_TOOL_NAME}` / `{MODIFY_CARD_TOOL_NAME}`。
3. `{SUBMIT_OPERATION_TOOL_NAME}`：用第一人称写清这次运转的结果。"""


#########################################################################################################################################
@final
class CardOperationSystem(ReactiveProcessor):
    """响应出牌：结算该牌的运转词缀，由持有者自己操作自己的牌堆。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlayCardsAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        """只处理带运转词缀的出牌：没有词缀就不该唤起任何结算。"""
        return (
            entity.has(PlayCardsAction)
            and entity.has(ActorComponent)
            and bool(entity.get(PlayCardsAction).card.engine_affixes)
        )

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("CardOperationSystem: 战斗未进行中，跳过运转结算")
            return

        for entity in entities:
            await self._run_resolution(entity)

    ####################################################################################################################################
    async def _run_resolution(self, entity: Entity) -> None:
        """驱动一次运转结算：提示词 → 工具调用 → 总结 → 牌堆变更记录。"""

        play_cards_action = entity.get(PlayCardsAction)
        card = play_cards_action.card

        for pile in PILES:
            _pile_cards(entity, pile)  # 缺组件在这里断言，不做降级

        round_number = len(self._game.current_dungeon_combat_room.combat.rounds or [])
        before = {pile: len(_pile_cards(entity, pile)) for pile in PILES}

        memory = self._game.get_agent_memory(entity)
        loop_id = make_loop_id(
            memory.messages, "card_operation", round_number, entity.name, card.name
        )
        start_index = len(memory.messages)

        ctx = OperationContext(owner_name=entity.name, played_card_name=card.name)
        prompt = build_operation_prompt(
            entity.name, card, _handle_list_piles(entity, ctx), round_number
        )

        try:
            result = await agent_loop(
                name=entity.name,
                input_message=prompt,
                messages=memory.messages,
                tools=[
                    LIST_PILES_TOOL,
                    COPY_CARD_TOOL,
                    MOVE_CARD_TOOL,
                    MODIFY_CARD_TOOL,
                    SUBMIT_OPERATION_TOOL,
                ],
                handlers={
                    LIST_PILES_TOOL_NAME: partial(_handle_list_piles, entity, ctx),
                    COPY_CARD_TOOL_NAME: partial(_handle_copy_card, entity, ctx),
                    MOVE_CARD_TOOL_NAME: partial(_handle_move_card, entity, ctx),
                    MODIFY_CARD_TOOL_NAME: partial(_handle_modify_card, entity, ctx),
                    SUBMIT_OPERATION_TOOL_NAME: partial(
                        _handle_submit_card_operation, ctx
                    ),
                },
                max_rounds=6,
                tool_choice="required",
                terminal_tools=[SUBMIT_OPERATION_TOOL],
                loop_id=loop_id,
            )
        except Exception as e:
            logger.error(f"[CardOperationSystem] agent_loop 异常: {e}")
            record_aborted_loop(
                self._game,
                entity,
                kind=RoundKind.CARD_OPERATION,
                loop_id=loop_id,
                reason=f"agent_loop 异常：{e}",
            )
            return

        if not result or not ctx.finished:
            logger.error("[CardOperationSystem] 结算未正常完成（未提交结果）")
            record_aborted_loop(
                self._game,
                entity,
                kind=RoundKind.CARD_OPERATION,
                loop_id=loop_id,
                reason="模型未在轮次上限内提交结算结果（未调用 submit_card_operation）",
            )
            return

        assert ctx.summary is not None, "submit 成功时 summary 必定存在"
        actions_log = "；".join(ctx.actions) if ctx.actions else "本次没有改动任何牌"

        compress_loop_to_summary(
            self._game,
            entity,
            start_index,
            summary=self._build_memory_summary(card, ctx),
            combat_log=actions_log,
            loop_id=loop_id,
        )

        # 事实层：容器真的变了才写一条（牌是私产，只写给主人）
        after = {pile: len(_pile_cards(entity, pile)) for pile in PILES}
        deltas = {pile: after[pile] - before[pile] for pile in PILES}
        if any(deltas.values()):
            record_pile_change(
                self._game,
                entity,
                change="card_operation",
                title=f"牌堆运转 · 「{card.name}」",
                lines=list(ctx.actions),
                deltas=deltas,
            )

        logger.info(
            f"[CardOperationSystem] {entity.name} 的「{card.name}」运转完成：{actions_log}"
        )

    ####################################################################################################################################
    def _build_memory_summary(self, card: Card, ctx: OperationContext) -> str:
        """整理成一条可长期保留的第一人称记忆。"""
        lines = [f"# 牌堆运转 · 「{card.name}」", "", f"我打出了「{card.name}」，"]
        summary = (ctx.summary or "").strip()
        lines.append(summary if summary else "（没有留下说明）")
        if ctx.unresolved:
            lines.append("")
            lines.append("没做到的部分：" + "；".join(ctx.unresolved))
        return "\n".join(lines)
