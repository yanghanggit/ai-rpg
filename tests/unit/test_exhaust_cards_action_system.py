"""ExhaustCardsActionSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    ActorComponent,
    DiscardPileComponent,
    ExhaustPileComponent,
    PlayCardsAction,
)
from src.ai_rpg.models import Card, TargetType
from src.ai_rpg.systems.exhaust_cards_action_system import ExhaustCardsActionSystem


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
    entity.add(DiscardPileComponent, name, [])
    entity.add(ExhaustPileComponent, name, [])
    return entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    game = MagicMock(spec=TCGGame)
    game.current_dungeon.is_ongoing = True
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> ExhaustCardsActionSystem:
    return ExhaustCardsActionSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExhaustCardsActionSystemSkip:
    """非 ongoing 状态时系统应跳过，不修改任何 pile。"""

    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustCardsActionSystem,
    ) -> None:
        mock_game.current_dungeon.is_ongoing = False
        entity = _make_entity(context, "英雄")
        card = _make_card("闪击", source="英雄", exhaust=True)
        entity.get(DiscardPileComponent).cards.append(card)
        entity.add(PlayCardsAction, "英雄", card, [], "")

        await system.react([entity])

        # 两个 pile 均不应变化
        assert len(entity.get(DiscardPileComponent).cards) == 1
        assert len(entity.get(ExhaustPileComponent).cards) == 0


class TestExhaustCardsActionSystemExhaustTrue:
    """exhaust=True 的自有牌：应从 DiscardPile 移入 ExhaustPile。"""

    @pytest.mark.asyncio
    async def test_exhaust_card_moves_to_exhaust_pile(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustCardsActionSystem,
    ) -> None:
        entity = _make_entity(context, "英雄")
        card = _make_card("终焉之击", source="英雄", exhaust=True)
        entity.get(DiscardPileComponent).cards.append(card)
        entity.add(PlayCardsAction, "英雄", card, [], "")

        await system.react([entity])

        assert card not in entity.get(DiscardPileComponent).cards
        assert card in entity.get(ExhaustPileComponent).cards

    @pytest.mark.asyncio
    async def test_exhaust_pile_accumulates(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustCardsActionSystem,
    ) -> None:
        """多次调用后 ExhaustPile 应累积。"""
        entity = _make_entity(context, "英雄")
        card1 = _make_card("消耗牌A", source="英雄", exhaust=True)
        card2 = _make_card("消耗牌B", source="英雄", exhaust=True)

        entity.get(DiscardPileComponent).cards.append(card1)
        entity.add(PlayCardsAction, "英雄", card1, [], "")
        await system.react([entity])

        entity.get(DiscardPileComponent).cards.append(card2)
        entity.replace(PlayCardsAction, "英雄", card2, [], "")
        await system.react([entity])

        exhaust = entity.get(ExhaustPileComponent)
        assert card1 in exhaust.cards
        assert card2 in exhaust.cards
        assert len(exhaust.cards) == 2


class TestExhaustCardsActionSystemExhaustFalse:
    """exhaust=False 的自有牌：DiscardPile 和 ExhaustPile 均不变。"""

    @pytest.mark.asyncio
    async def test_normal_card_not_moved(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustCardsActionSystem,
    ) -> None:
        entity = _make_entity(context, "英雄")
        card = _make_card("普通斩击", source="英雄", exhaust=False)
        entity.get(DiscardPileComponent).cards.append(card)
        entity.add(PlayCardsAction, "英雄", card, [], "")

        await system.react([entity])

        assert card in entity.get(DiscardPileComponent).cards
        assert len(entity.get(ExhaustPileComponent).cards) == 0


class TestExhaustCardsActionSystemForeignCard:
    """exhaust=True 的外来牌（source != entity.name）：
    MoveToDiscardPileSystem 将其写入 DiscardPile，ExhaustCardsActionSystem 应将其
    移入 ExhaustPile（战斗结束后由 CombatPileTeardownSystem 统一清理子堆，无需 source 过滤）。"""

    @pytest.mark.asyncio
    async def test_foreign_exhaust_card_moves_to_exhaust_pile(
        self,
        context: Context,
        mock_game: MagicMock,
        system: ExhaustCardsActionSystem,
    ) -> None:
        entity = _make_entity(context, "英雄")
        foreign_card = _make_card("外来秘术", source="他人", exhaust=True)
        # MoveToDiscardPileSystem 已无条件将出牌写入 DiscardPile
        entity.get(DiscardPileComponent).cards.append(foreign_card)
        entity.add(PlayCardsAction, "英雄", foreign_card, [], "")

        await system.react([entity])

        assert foreign_card not in entity.get(DiscardPileComponent).cards
        assert foreign_card in entity.get(ExhaustPileComponent).cards
