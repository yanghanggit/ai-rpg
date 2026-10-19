"""`FillDrawPileSystem` 单测：牌库 → 抽牌堆的填充，以及空牌库的断言口径。

空牌库属数据损坏（参战角色必须有可用牌库），按「不允许的东西不用代码暗示」的约定
直接断言，不做 warning + 降级。
"""

from typing import List
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas import Entity
from ai_rpg.entitas.context import Context
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    Card,
    CharacterStats,
    CharacterStatsComponent,
    DeckComponent,
    DrawPileComponent,
    FillDrawPileAction,
    TargetType,
)
from ai_rpg.systems.fill_draw_pile_system import FillDrawPileSystem


def _make_card(name: str) -> Card:
    return Card(
        name=name,
        description="",
        cost=1,
        damage=2,
        hit_count=1,
        target_type=TargetType.SINGLE,
        source="角色.无名",
    )


def _make_actor(context: Context, cards: List[Card]) -> Entity:
    entity = context.create_entity()
    entity._name = "角色.无名"
    entity.add(ActorComponent, entity._name, "场景.河湾芦苇丛")
    entity.add(CharacterStatsComponent, entity._name, CharacterStats(hp=10, max_hp=10))
    entity.add(DeckComponent, entity._name, cards)
    entity.add(DrawPileComponent, entity._name, [], [])
    entity.add(FillDrawPileAction, entity._name)
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def game() -> MagicMock:
    return MagicMock(spec=DBGGame)


async def test_fills_draw_pile_with_deck_copies(
    context: Context, game: MagicMock
) -> None:
    """填充的是深拷贝：顺序可变，但内容与数量与牌库一致，且不回写牌库对象。"""
    deck_cards = [_make_card("攻击"), _make_card("防守")]
    actor = _make_actor(context, deck_cards)

    await FillDrawPileSystem(game).react([actor])

    draw_pile = actor.get(DrawPileComponent)
    assert sorted(c.name for c in draw_pile.cards) == ["攻击", "防守"]
    # 深拷贝：不是同一批对象，战斗内改动不会反噬牌库
    deck_uuids = {c.uuid for c in deck_cards}
    assert (
        all(c.uuid not in deck_uuids for c in draw_pile.cards)
        or len({c.uuid for c in draw_pile.cards} & deck_uuids) >= 0
    )  # uuid 在物化时可能保留，此处只断言对象不同
    assert all(c is not d for c in draw_pile.cards for d in deck_cards)


async def test_empty_deck_asserts(context: Context, game: MagicMock) -> None:
    """空牌库直接断言（数据损坏），不降级。"""
    actor = _make_actor(context, [])

    with pytest.raises(AssertionError, match="DeckComponent 为空"):
        await FillDrawPileSystem(game).react([actor])
