"""MoveToDiscardPileSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    DiscardPileComponent,
    HandComponent,
    PlayCardsAction,
)
from src.ai_rpg.models import Card, TargetType
from src.ai_rpg.systems.move_to_discard_pile_system import MoveToDiscardPileSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(name: str, source: str, *, exhaust: bool = False) -> Card:
    return Card(
        name=name,
        description="测试卡牌",
        affixes=[],
        playable=True,
        exhaust=exhaust,
        damage_dealt=1,
        hit_count=1,
        target_type=TargetType.ENEMY_SINGLE,
        source=source,
    )


def _make_entity(context: Context, name: str) -> Entity:
    """创建带必要战斗组件的角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "dungeon")
    entity.add(HandComponent, name, [], 1)
    entity.add(DiscardPileComponent, name, [])
    return entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.current_dungeon.is_ongoing = True
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> MoveToDiscardPileSystem:
    return MoveToDiscardPileSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMoveToDiscardPileSystemSkip:
    """非 ongoing 状态时系统应跳过，不修改任何 pile。"""

    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: MoveToDiscardPileSystem,
    ) -> None:
        mock_game.current_dungeon.is_ongoing = False
        entity = _make_entity(context, "英雄")
        card = _make_card("闪击", source="英雄")
        entity.get(HandComponent).cards.append(card)
        entity.add(PlayCardsAction, "英雄", card, [])

        await system.react([entity])

        assert card in entity.get(HandComponent).cards
        assert len(entity.get(DiscardPileComponent).cards) == 0


class TestMoveToDiscardPileSystemOwnCard:
    """自有牌（source == entity.name）：应从 Hand 移除并写入 DiscardPile。"""

    @pytest.mark.asyncio
    async def test_card_removed_from_hand(
        self,
        context: Context,
        mock_game: MagicMock,
        system: MoveToDiscardPileSystem,
    ) -> None:
        entity = _make_entity(context, "英雄")
        card = _make_card("斩击", source="英雄")
        entity.get(HandComponent).cards.append(card)
        entity.add(PlayCardsAction, "英雄", card, [])

        await system.react([entity])

        assert card not in entity.get(HandComponent).cards

    @pytest.mark.asyncio
    async def test_card_added_to_discard_pile(
        self,
        context: Context,
        mock_game: MagicMock,
        system: MoveToDiscardPileSystem,
    ) -> None:
        entity = _make_entity(context, "英雄")
        card = _make_card("斩击", source="英雄")
        entity.get(HandComponent).cards.append(card)
        entity.add(PlayCardsAction, "英雄", card, [])

        await system.react([entity])

        assert card in entity.get(DiscardPileComponent).cards


class TestMoveToDiscardPileSystemForeignCard:
    """外来牌（source != entity.name）：也应写入 DiscardPile（无 source 过滤）。"""

    @pytest.mark.asyncio
    async def test_foreign_card_added_to_discard_pile(
        self,
        context: Context,
        mock_game: MagicMock,
        system: MoveToDiscardPileSystem,
    ) -> None:
        entity = _make_entity(context, "英雄")
        foreign_card = _make_card("外来秘术", source="他人")
        entity.get(HandComponent).cards.append(foreign_card)
        entity.add(PlayCardsAction, "英雄", foreign_card, [])

        await system.react([entity])

        assert foreign_card not in entity.get(HandComponent).cards
        assert foreign_card in entity.get(DiscardPileComponent).cards
