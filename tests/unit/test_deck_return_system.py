"""DeckReturnSystem 单元测试。"""

import pytest
from unittest.mock import MagicMock
from src.ai_rpg.entitas.context import Context
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    ActorComponent,
    DeckComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
)
from src.ai_rpg.models import Card, TargetType
from src.ai_rpg.systems.deck_return_system import DeckReturnSystem
from src.ai_rpg.entitas import Entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    """提供真实 ECS Context，使 Group / Matcher 自动更新行为生效。"""
    return Context()


@pytest.fixture()
def mock_game(context: Context) -> MagicMock:
    """Mock TCGGame，将 get_group() 代理到真实 Context。"""
    game = MagicMock(spec=TCGGame)
    game.get_group.side_effect = context.get_group
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> DeckReturnSystem:
    return DeckReturnSystem(mock_game)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_card(name: str, source: str) -> Card:
    return Card(
        name=name,
        description="测试卡牌",
        affixes=[],
        playable=True,
        discardable=True,
        damage_dealt=1,
        hit_count=1,
        target_type=TargetType.ENEMY_SINGLE,
        source=source,
    )


def _make_combat_entity(context: Context, name: str) -> Entity:
    """创建持有全部战斗组件的角色实体（模拟战斗中状态）。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "home")
    entity.add(DeckComponent, name, [])
    entity.add(DrawPileComponent, name, [])
    entity.add(DiscardPileComponent, name, [])
    entity.add(ExhaustPileComponent, name, [])
    return entity


# ---------------------------------------------------------------------------
# Tests — skipping behavior
# ---------------------------------------------------------------------------


class TestDeckReturnSystemSkip:
    """非战斗后阶段时的跳过行为。"""

    @pytest.mark.asyncio
    async def test_skips_when_not_post_combat(
        self, mock_game: MagicMock, system: DeckReturnSystem
    ) -> None:
        """当 is_post_combat 为 False 时，应跳过并不调用 get_group。"""
        mock_game.current_dungeon.is_post_combat = False

        await system.execute()

        mock_game.get_group.assert_not_called()


# ---------------------------------------------------------------------------
# Tests — pile removal (core behavior)
# ---------------------------------------------------------------------------


class TestDeckReturnSystemPileRemoval:
    """战斗结束后三个 Pile 组件应被移除。"""

    @pytest.mark.asyncio
    async def test_removes_draw_pile_component(
        self, context: Context, mock_game: MagicMock, system: DeckReturnSystem
    ) -> None:
        """执行后实体不应再持有 DrawPileComponent。"""
        mock_game.current_dungeon.is_post_combat = True
        entity = _make_combat_entity(context, "英雄")

        await system.execute()

        assert not entity.has(DrawPileComponent)

    @pytest.mark.asyncio
    async def test_removes_discard_pile_component(
        self, context: Context, mock_game: MagicMock, system: DeckReturnSystem
    ) -> None:
        """执行后实体不应再持有 DiscardPileComponent。"""
        mock_game.current_dungeon.is_post_combat = True
        entity = _make_combat_entity(context, "英雄")

        await system.execute()

        assert not entity.has(DiscardPileComponent)

    @pytest.mark.asyncio
    async def test_removes_exhaust_pile_component(
        self, context: Context, mock_game: MagicMock, system: DeckReturnSystem
    ) -> None:
        """执行后实体不应再持有 ExhaustPileComponent。"""
        mock_game.current_dungeon.is_post_combat = True
        entity = _make_combat_entity(context, "英雄")

        await system.execute()

        assert not entity.has(ExhaustPileComponent)

    @pytest.mark.asyncio
    async def test_deck_component_retained(
        self, context: Context, mock_game: MagicMock, system: DeckReturnSystem
    ) -> None:
        """执行后实体应仍持有 DeckComponent（跨战斗持久牌库）。"""
        mock_game.current_dungeon.is_post_combat = True
        entity = _make_combat_entity(context, "英雄")

        await system.execute()

        assert entity.has(DeckComponent)

    @pytest.mark.asyncio
    async def test_own_cards_returned_to_deck(
        self, context: Context, mock_game: MagicMock, system: DeckReturnSystem
    ) -> None:
        """自有牌应被归还至 DeckComponent。"""
        mock_game.current_dungeon.is_post_combat = True
        entity = _make_combat_entity(context, "英雄")
        card1 = _make_card("闪击", source="英雄")
        card2 = _make_card("格挡", source="英雄")
        entity.get(DrawPileComponent).cards.append(card1)
        entity.get(DiscardPileComponent).cards.append(card2)

        await system.execute()

        deck = entity.get(DeckComponent)
        assert len(deck.cards) == 2
        assert card1 in deck.cards
        assert card2 in deck.cards

    @pytest.mark.asyncio
    async def test_foreign_cards_discarded(
        self, context: Context, mock_game: MagicMock, system: DeckReturnSystem
    ) -> None:
        """外来牌（source != 角色名）不应归还 DeckComponent。"""
        mock_game.current_dungeon.is_post_combat = True
        entity = _make_combat_entity(context, "英雄")
        own_card = _make_card("闪击", source="英雄")
        foreign_card = _make_card("外来技", source="他人")
        entity.get(DrawPileComponent).cards.extend([own_card, foreign_card])

        await system.execute()

        deck = entity.get(DeckComponent)
        assert own_card in deck.cards
        assert foreign_card not in deck.cards

    @pytest.mark.asyncio
    async def test_multiple_entities_all_piles_removed(
        self, context: Context, mock_game: MagicMock, system: DeckReturnSystem
    ) -> None:
        """多个实体应全部被处理，Pile 组件全部移除。"""
        mock_game.current_dungeon.is_post_combat = True
        hero = _make_combat_entity(context, "英雄")
        monster = _make_combat_entity(context, "哥布林")

        await system.execute()

        for entity in (hero, monster):
            assert not entity.has(DrawPileComponent)
            assert not entity.has(DiscardPileComponent)
            assert not entity.has(ExhaustPileComponent)
            assert entity.has(DeckComponent)
