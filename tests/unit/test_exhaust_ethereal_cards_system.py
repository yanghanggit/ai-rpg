"""ExhaustEtherealCardsSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    ExhaustPileComponent,
    HandComponent,
    PassTurnAction,
)
from src.ai_rpg.models import Card, TargetType
from src.ai_rpg.systems.exhaust_ethereal_cards_system import ExhaustEtherealCardsSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(name: str, *, ethereal: bool = False) -> Card:
    return Card(
        name=name,
        description="测试卡牌",
        playable=True,
        ethereal=ethereal,
        damage=1,
        hit_count=1,
        target_type=TargetType.SINGLE,
    )


def _make_entity(context: Context, name: str) -> Entity:
    """创建带必要战斗组件的角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "dungeon")
    entity.add(HandComponent, name, [])
    entity.add(ExhaustPileComponent, name, [])
    entity.add(PassTurnAction, name)
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
    game.current_dungeon_combat_room.combat.is_ongoing = True
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> ExhaustEtherealCardsSystem:
    return ExhaustEtherealCardsSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExhaustEtherealCardsSystemSkip:
    """非 ongoing 状态时系统应跳过，不修改任何 pile。"""

    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustEtherealCardsSystem,
    ) -> None:
        mock_game.current_dungeon_combat_room.combat.is_ongoing = False
        entity = _make_entity(context, "英雄")
        card = _make_card("虚无斩", ethereal=True)
        entity.get(HandComponent).cards.append(card)

        await system.react([entity])

        assert card in entity.get(HandComponent).cards
        assert len(entity.get(ExhaustPileComponent).cards) == 0


class TestExhaustEtherealCardsSystemEtherealTrue:
    """ethereal=True 的牌：pass turn 时应从 Hand 移入 ExhaustPile。"""

    @pytest.mark.asyncio
    async def test_ethereal_card_moves_to_exhaust_pile(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustEtherealCardsSystem,
    ) -> None:
        entity = _make_entity(context, "英雄")
        card = _make_card("虚无斩", ethereal=True)
        entity.get(HandComponent).cards.append(card)

        await system.react([entity])

        assert card not in entity.get(HandComponent).cards
        assert card in entity.get(ExhaustPileComponent).cards

    @pytest.mark.asyncio
    async def test_exhaust_pile_accumulates(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustEtherealCardsSystem,
    ) -> None:
        """多次 pass 时 ExhaustPile 应累积。"""
        entity = _make_entity(context, "英雄")
        card1 = _make_card("虚无斩A", ethereal=True)
        card2 = _make_card("虚无斩B", ethereal=True)

        entity.get(HandComponent).cards.append(card1)
        await system.react([entity])

        entity.get(HandComponent).cards.append(card2)
        await system.react([entity])

        exhaust = entity.get(ExhaustPileComponent)
        assert card1 in exhaust.cards
        assert card2 in exhaust.cards
        assert len(exhaust.cards) == 2


class TestExhaustEtherealCardsSystemEtherealFalse:
    """ethereal=False 的牌：pass turn 后仍留在 Hand，不进入 ExhaustPile。"""

    @pytest.mark.asyncio
    async def test_normal_card_stays_in_hand(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustEtherealCardsSystem,
    ) -> None:
        entity = _make_entity(context, "英雄")
        card = _make_card("普通斩击", ethereal=False)
        entity.get(HandComponent).cards.append(card)

        await system.react([entity])

        assert card in entity.get(HandComponent).cards
        assert len(entity.get(ExhaustPileComponent).cards) == 0

    @pytest.mark.asyncio
    async def test_mixed_hand_only_ethereal_moved(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustEtherealCardsSystem,
    ) -> None:
        """混合手牌：仅 ethereal=True 的牌被移走，其余保留。"""
        entity = _make_entity(context, "英雄")
        ethereal_card = _make_card("虚无斩", ethereal=True)
        normal_card = _make_card("普通斩击", ethereal=False)
        entity.get(HandComponent).cards.extend([ethereal_card, normal_card])

        await system.react([entity])

        assert ethereal_card not in entity.get(HandComponent).cards
        assert normal_card in entity.get(HandComponent).cards
        assert ethereal_card in entity.get(ExhaustPileComponent).cards
        assert normal_card not in entity.get(ExhaustPileComponent).cards
