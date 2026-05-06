"""DestroyEntitySystem 单元测试。"""

import pytest
from unittest.mock import MagicMock

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.game.rpg_game import RPGGame
from src.ai_rpg.models.components import DestroyComponent
from src.ai_rpg.systems.destroy_entity_system import DestroyEntitySystem
from tests.unit.test_components import Position


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    """提供真实 ECS Context。"""
    return Context()


@pytest.fixture()
def mock_game(context: Context) -> MagicMock:
    """Mock RPGGame：get_group() 代理到真实 Context，destroy_entity() 同时调用真实 Context 的销毁。"""
    game = MagicMock(spec=RPGGame)
    game.get_group.side_effect = context.get_group
    game.destroy_entity.side_effect = context.destroy_entity
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> DestroyEntitySystem:
    return DestroyEntitySystem(mock_game)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDestroyEntitySystem:
    """DestroyEntitySystem.execute() 的单元测试。"""

    @pytest.mark.asyncio
    async def test_execute_empty_world(self, system: DestroyEntitySystem) -> None:
        """无实体时 execute() 应正常完成，不调用 destroy_entity()。"""
        await system.execute()

    @pytest.mark.asyncio
    async def test_execute_destroys_single_marked_entity(
        self, context: Context, mock_game: MagicMock, system: DestroyEntitySystem
    ) -> None:
        """持有 DestroyComponent 的实体执行后应被销毁。"""
        entity = context.create_entity()
        entity.add(DestroyComponent, "target")

        await system.execute()

        mock_game.destroy_entity.assert_called_once_with(entity)
        assert not context.has_entity(entity)

    @pytest.mark.asyncio
    async def test_execute_destroys_multiple_marked_entities(
        self, context: Context, mock_game: MagicMock, system: DestroyEntitySystem
    ) -> None:
        """多个持有 DestroyComponent 的实体全部应被销毁。"""
        entity_a = context.create_entity()
        entity_a.add(DestroyComponent, "a")
        entity_b = context.create_entity()
        entity_b.add(DestroyComponent, "b")
        entity_c = context.create_entity()
        entity_c.add(DestroyComponent, "c")

        await system.execute()

        assert mock_game.destroy_entity.call_count == 3
        assert not context.has_entity(entity_a)
        assert not context.has_entity(entity_b)
        assert not context.has_entity(entity_c)

    @pytest.mark.asyncio
    async def test_execute_ignores_entities_without_destroy_component(
        self, context: Context, mock_game: MagicMock, system: DestroyEntitySystem
    ) -> None:
        """不持有 DestroyComponent 的实体不应被销毁。"""
        entity = context.create_entity()
        entity.add(Position, 1.0, 2.0)

        await system.execute()

        mock_game.destroy_entity.assert_not_called()
        assert context.has_entity(entity)

    @pytest.mark.asyncio
    async def test_execute_only_destroys_marked_entities(
        self, context: Context, mock_game: MagicMock, system: DestroyEntitySystem
    ) -> None:
        """混合场景：仅销毁持有 DestroyComponent 的实体，保留其他实体。"""
        to_destroy = context.create_entity()
        to_destroy.add(DestroyComponent, "bye")

        to_keep = context.create_entity()
        to_keep.add(Position, 0.0, 0.0)

        await system.execute()

        mock_game.destroy_entity.assert_called_once_with(to_destroy)
        assert not context.has_entity(to_destroy)
        assert context.has_entity(to_keep)

    @pytest.mark.asyncio
    async def test_execute_calls_destroy_entity_not_remove_component(
        self, context: Context, mock_game: MagicMock, system: DestroyEntitySystem
    ) -> None:
        """execute() 应通过 game.destroy_entity() 销毁实体，而非仅移除组件。"""
        entity = context.create_entity()
        entity.add(DestroyComponent, "x")

        await system.execute()

        # destroy_entity 被调用，而非 entity.remove()
        mock_game.destroy_entity.assert_called_once()
