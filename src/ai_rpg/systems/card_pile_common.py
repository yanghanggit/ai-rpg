"""牌堆变更记录：卡牌容器只要有变动，就写一条只给容器主人的说明。

判据是「谁的容器被改」，与「谁触发的」无关：别人把可传递牌塞进我的手牌，同样算我的容器
变动。消息只写给主人，从不广播——别人的牌堆不关我的事。

已有更精确记录的动作（出牌决策、收到卡、领取战利品、装备/消耗品物化）不在此重复写，
否则一次动作会落三条记忆。
"""

import json
from enum import StrEnum
from typing import Dict, Final, List, Mapping, Sequence, Tuple

from ..entitas import Entity
from ..game.dbg_game import DBGGame
from ..llm import ToolDefinition, ToolFunction
from ..models import (
    Card,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    HumanMessage,
)


#######################################################################################################################################
# 容器标识：审计用英文键，正文用中文名
#######################################################################################################################################
class Pile(StrEnum):
    """牌堆 / 容器标识。值即审计用的英文键，`PILE_LABELS` 提供中文名。"""

    DECK = "deck"
    SPOILS = "spoils"
    DRAW = "draw_pile"
    RETAINED = "retained"
    HAND = "hand"
    DISCARD = "discard_pile"
    EXHAUST = "exhaust_pile"


PILE_DECK: Final[str] = Pile.DECK
PILE_SPOILS: Final[str] = Pile.SPOILS
PILE_DRAW: Final[str] = Pile.DRAW
PILE_RETAINED: Final[str] = Pile.RETAINED
PILE_HAND: Final[str] = Pile.HAND
PILE_DISCARD: Final[str] = Pile.DISCARD
PILE_EXHAUST: Final[str] = Pile.EXHAUST

PILE_LABELS: Final[Dict[str, str]] = {
    PILE_DECK: "牌库",
    PILE_SPOILS: "待领取",
    PILE_DRAW: "抽牌堆",
    PILE_RETAINED: "保留队列",
    PILE_HAND: "手牌",
    PILE_DISCARD: "弃牌堆",
    PILE_EXHAUST: "消耗堆",
}


#######################################################################################################################################
def format_card_names(cards: Sequence[Card]) -> str:
    """把卡牌列成「A」「B」「C」，供记忆正文引用具体牌。"""
    return "".join(f"「{card.name}」" for card in cards)


#######################################################################################################################################
def build_pile_change_tag(change: str, deltas: Mapping[str, int]) -> str:
    """生成 `card_pile_change` 标记值：变动原因 + 各容器的净增减（零变动不记）。"""
    nonzero = {pile: delta for pile, delta in deltas.items() if delta}
    return json.dumps(
        {"change": change, "deltas": nonzero},
        ensure_ascii=False,
        sort_keys=True,
    )


#######################################################################################################################################
def record_pile_change(
    game: DBGGame,
    owner: Entity,
    *,
    change: str,
    title: str,
    lines: Sequence[str],
    deltas: Mapping[str, int],
) -> None:
    """把一次容器变更写成只给主人的记忆（`title` 作首行，`lines` 逐行说明）。"""
    assert deltas and any(
        deltas.values()
    ), f"{owner.name} 的牌堆变更没有净增减，不该写记忆（change={change}）"
    content = "\n".join([f"# {title}", *lines])
    game.add_human_message(
        entity=owner,
        human_message=HumanMessage(
            content=content,
            card_pile_change=build_pile_change_tag(change, deltas),
        ),
    )


#######################################################################################################################################
def record_round_end_discard(
    game: DBGGame,
    settlements: Sequence[Tuple[Entity, Sequence[Card], Sequence[Card]]],
) -> None:
    """回合末清手牌：把每张手牌的去向告诉主人（进弃牌堆 / 留到下回合）。"""
    for owner, discarded, retained in settlements:
        if not discarded and not retained:
            continue
        discard_size = (
            len(owner.get(DiscardPileComponent).cards)
            if owner.has(DiscardPileComponent)
            else 0
        )
        lines: List[str] = []
        if discarded:
            lines.append(
                f"{format_card_names(list(discarded))}进入弃牌堆（弃牌堆 {discard_size} 张）。"
            )
        if retained:
            lines.append(
                f"{format_card_names(list(retained))}保留到下回合，抽牌时会先回到手牌。"
            )
        lines.append("手牌已清空。")
        record_pile_change(
            game,
            owner,
            change="round_end_discard",
            title="回合结束 · 清手牌",
            lines=lines,
            deltas={
                PILE_HAND: -(len(discarded) + len(retained)),
                PILE_DISCARD: len(discarded),
                PILE_RETAINED: len(retained),
            },
        )


#######################################################################################################################################
def format_pile_counts(counts: Mapping[str, int]) -> str:
    """把若干容器余量拼成「手牌 4 / 抽牌堆 5」，零余量的容器也照实写出。"""
    return " / ".join(f"{PILE_LABELS[pile]} {count}" for pile, count in counts.items())


#######################################################################################################################################
# 牌堆读取工具：上面记「流转」，这里按需给「当前内容」（取舍见 docs/wiki/card.md）。
#######################################################################################################################################
PILE_READABLE: Final[Tuple[str, ...]] = (
    PILE_DRAW,
    PILE_DISCARD,
    PILE_EXHAUST,
    PILE_RETAINED,
)

# 各牌堆的顺序语义：抽牌堆 / 保留队列的顺序有意义，其余两堆只当集合看。
_PILE_ORDER_NOTES: Final[Dict[str, str]] = {
    PILE_DRAW: "，先抽最前",
    PILE_RETAINED: "，下次抽牌先回手",
}

READ_PILES_TOOL_NAME: Final[str] = "read_piles"

READ_PILES_TOOL: Final[ToolDefinition] = ToolDefinition(
    function=ToolFunction(
        name=READ_PILES_TOOL_NAME,
        description="读取你自己牌堆的当前内容（抽牌堆 / 弃牌堆 / 消耗堆 / 保留队列）。只读，不改动任何牌、不消耗能量；用于判断接下来可能抽到什么、还剩哪些牌可用。",
        parameters={
            "type": "object",
            "properties": {
                "pile": {
                    "type": "string",
                    "enum": list(PILE_READABLE),
                    "description": "可选：只看某一个牌堆；省略则全部返回",
                }
            },
            "required": [],
        },
    )
)


#######################################################################################################################################
def read_pile_cards(entity: Entity, pile: str) -> List[Card]:
    """取某个牌堆里的牌（只读；缺组件按空堆处理）。"""
    match pile:
        case Pile.DRAW:
            return (
                entity.get(DrawPileComponent).cards
                if entity.has(DrawPileComponent)
                else []
            )
        case Pile.RETAINED:
            return (
                entity.get(DrawPileComponent).retained_cards
                if entity.has(DrawPileComponent)
                else []
            )
        case Pile.DISCARD:
            return (
                entity.get(DiscardPileComponent).cards
                if entity.has(DiscardPileComponent)
                else []
            )
        case Pile.EXHAUST:
            return (
                entity.get(ExhaustPileComponent).cards
                if entity.has(ExhaustPileComponent)
                else []
            )
        case _:
            return []


#######################################################################################################################################
def format_pile_report_line(pile: str, cards: Sequence[Card]) -> str:
    """一行一个牌堆：名称（张数 + 顺序说明）+ 牌名与费用。"""
    note = _PILE_ORDER_NOTES.get(pile, "")
    contents = "、".join(f"「{c.name}」(费{c.cost})" for c in cards) or "（空）"
    return f"{PILE_LABELS[pile]}（{len(cards)} 张{note}）：{contents}"


#######################################################################################################################################
def handle_read_piles(entity: Entity, pile: str = "") -> str:
    """`read_piles` 工具的处理器：返回自己各牌堆的只读快照（可只读一个）。"""
    if pile and pile not in PILE_READABLE:
        return f"错误：未知牌堆 {pile!r}（可选：{'、'.join(PILE_READABLE)}；省略 pile 则全部返回）"
    piles = [pile] if pile else list(PILE_READABLE)
    lines = [format_pile_report_line(p, read_pile_cards(entity, p)) for p in piles]
    return "\n".join(["# 你的牌堆", *lines])
