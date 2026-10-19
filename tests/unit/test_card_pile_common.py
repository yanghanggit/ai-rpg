"""牌堆变更记录（`card_pile_common`）单测。

口径：容器变了就写一条只给主人的说明；没有净变动就不写；标记值只记原因与净增减。
"""

import json
from typing import List
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas import Entity
from ai_rpg.entitas.context import Context
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    Card,
    DiscardPileComponent,
    DrawPileComponent,
    TargetType,
)
from ai_rpg.systems.card_pile_common import (
    PILE_DISCARD,
    PILE_DRAW,
    PILE_HAND,
    PILE_LABELS,
    PILE_RETAINED,
    build_pile_change_tag,
    format_card_names,
    format_pile_counts,
    record_pile_change,
    record_round_end_discard,
)


def _make_card(name: str, *, retain: bool = False) -> Card:
    return Card(
        name=name,
        description="",
        cost=1,
        damage=2,
        hit_count=1,
        retain=retain,
        target_type=TargetType.SINGLE,
        source="角色.无名",
    )


def _make_owner(context: Context, *, cards: int = 0, retained: int = 0) -> Entity:
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(DrawPileComponent, entity._name, [], [])
    entity.add(DiscardPileComponent, entity._name, [])
    draw_pile = entity.get(DrawPileComponent)
    draw_pile.cards.extend(_make_card(f"牌{index}") for index in range(cards))
    draw_pile.retained_cards.extend(
        _make_card(f"留{index}", retain=True) for index in range(retained)
    )
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def game() -> MagicMock:
    return MagicMock(spec=DBGGame)


def test_tag_drops_zero_deltas() -> None:
    """净增减为 0 的容器不进标记，标记只记真正动过的容器。"""
    tag = json.loads(
        build_pile_change_tag(
            "draw_cards", {PILE_DRAW: -3, PILE_HAND: 3, PILE_DISCARD: 0}
        )
    )
    assert tag == {"change": "draw_cards", "deltas": {PILE_DRAW: -3, PILE_HAND: 3}}


def test_format_card_names_and_counts() -> None:
    """正文引用具体牌名；余量按「容器 数量」拼接。"""
    cards = [_make_card("攻击"), _make_card("防守")]
    assert format_card_names(cards) == "「攻击」「防守」"
    assert format_pile_counts({PILE_HAND: 2, PILE_DRAW: 7}) == "手牌 2 / 抽牌堆 7"
    assert set(PILE_LABELS) >= {PILE_HAND, PILE_DRAW, PILE_DISCARD, PILE_RETAINED}


def test_record_pile_change_writes_self_only_message(
    context: Context, game: MagicMock
) -> None:
    """写入的是本人记忆：首行标题、其余逐行说明，标记带原因与净增减。"""
    owner = _make_owner(context, cards=3)

    record_pile_change(
        game,
        owner,
        change="draw_cards",
        title="第 1 回合 · 抽牌",
        lines=["新抽 2 张：「攻击」「防守」", "手牌 2 张。"],
        deltas={PILE_DRAW: -2, PILE_HAND: 2},
    )

    game.add_human_message.assert_called_once()
    kwargs = game.add_human_message.call_args.kwargs
    assert kwargs["entity"] is owner
    message = kwargs["human_message"]
    assert message.content.splitlines() == [
        "# 第 1 回合 · 抽牌",
        "新抽 2 张：「攻击」「防守」",
        "手牌 2 张。",
    ]
    assert json.loads(message.card_pile_change) == {
        "change": "draw_cards",
        "deltas": {PILE_DRAW: -2, PILE_HAND: 2},
    }


def test_record_pile_change_asserts_on_no_net_change(
    context: Context, game: MagicMock
) -> None:
    """没有净变动的「变更」是数据错误，不写空消息。"""
    owner = _make_owner(context, cards=1)

    with pytest.raises(AssertionError, match="没有净增减"):
        record_pile_change(
            game,
            owner,
            change="draw_cards",
            title="不该发生",
            lines=["什么也没发生"],
            deltas={PILE_DRAW: 0, PILE_HAND: 0},
        )


def test_round_end_discard_reports_both_destinations(
    context: Context, game: MagicMock
) -> None:
    """回合末清手牌：弃掉的进弃牌堆，保留的进下回合保留队列，两者都写清楚。"""
    owner = _make_owner(context, cards=2)
    discarded: List[Card] = [_make_card("攻击"), _make_card("防守")]
    retained: List[Card] = [_make_card("守势", retain=True)]
    # 与 clear_round_state 一致：先入堆，再写记录（正文里的余量是变更后的）
    owner.get(DiscardPileComponent).cards.extend(discarded)

    record_round_end_discard(game, [(owner, discarded, retained)])

    kwargs = game.add_human_message.call_args.kwargs
    content = kwargs["human_message"].content
    assert content.splitlines()[0] == "# 回合结束 · 清手牌"
    assert "「攻击」「防守」进入弃牌堆（弃牌堆 2 张）" in content
    assert "「守势」保留到下回合" in content
    assert "手牌已清空" in content
    assert json.loads(kwargs["human_message"].card_pile_change)["deltas"] == {
        PILE_HAND: -3,
        PILE_DISCARD: 2,
        PILE_RETAINED: 1,
    }


def test_round_end_discard_skips_empty_hands(context: Context, game: MagicMock) -> None:
    """没有手牌可清就不写消息（避免每回合给全员刷一条空记录）。"""
    owner = _make_owner(context, cards=0)

    record_round_end_discard(game, [(owner, [], [])])

    game.add_human_message.assert_not_called()
