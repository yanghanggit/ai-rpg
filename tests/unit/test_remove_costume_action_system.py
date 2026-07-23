"""RemoveCostumeActionSystem 单元测试。"""

from typing import List, Optional
from unittest.mock import MagicMock
import pytest
from src.ai_rpg.entitas import Entity
from src.ai_rpg.game.rpg_entity_manager import RPGEntityManager
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    AppearanceComponent,
    WornCostumeComponent,
    StorageComponent,
    RemoveCostumeAction,
)
from src.ai_rpg.models.items import CostumeItem
from src.ai_rpg.systems.remove_costume_action_system import (
    RemoveCostumeActionSystem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_BODY = "人类基础外形"
_COSTUME = CostumeItem(name="铁甲", description="坚固的铁制盔甲")


def _make_actor_entity(
    entity_manager: RPGEntityManager,
    name: str,
    appearance: str = _BASE_BODY,
) -> Entity:
    """创建一个带有 AppearanceComponent 的实体。"""
    entity = entity_manager._create_entity(name)
    entity.add(AppearanceComponent, name, _BASE_BODY, appearance)
    return entity


def _make_storage_entity(
    entity_manager: RPGEntityManager,
    items: Optional[List[CostumeItem]] = None,
) -> Entity:
    """创建带有 StorageComponent 的储物箱实体。"""
    entity = entity_manager._create_entity("storage")
    entity.add(StorageComponent, "storage", list(items or []))
    return entity


def _make_stage_entity(
    entity_manager: RPGEntityManager, name: str = "测试场景"
) -> Entity:
    """创建一个用于 resolve_stage_entity 返回值的场景实体。"""
    return entity_manager._create_entity(name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def entity_manager() -> RPGEntityManager:
    """提供真实 RPGEntityManager，支持 get_group 和 get_entity_by_name。"""
    return RPGEntityManager()


@pytest.fixture()
def mock_game(entity_manager: RPGEntityManager) -> MagicMock:
    """Mock DBGGame，代理 ECS 操作到真实 RPGEntityManager。"""
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = entity_manager.get_group
    game.get_entity_by_name.side_effect = entity_manager.get_entity_by_name
    game.get_agent_context.return_value = MagicMock(context=[])
    game.get_storage_entity.return_value = None
    game.resolve_stage_entity.return_value = _make_stage_entity(entity_manager)
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> RemoveCostumeActionSystem:
    return RemoveCostumeActionSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests — RemoveCostumeActionSystem._remove_costume
# ---------------------------------------------------------------------------


class TestRemoveCostume:
    """RemoveCostumeActionSystem._remove_costume() 的单元测试。"""

    def test_skips_when_no_costume(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: RemoveCostumeActionSystem,
    ) -> None:
        """没有 WornCostumeComponent 的实体应静默跳过，不调用 broadcast_to_stage。"""
        entity = _make_actor_entity(entity_manager, "hero")

        system._remove_costume(entity)

        mock_game.broadcast_to_stage.assert_not_called()

    def test_removes_costume_component(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: RemoveCostumeActionSystem,
    ) -> None:
        """有 WornCostumeComponent 时，执行后组件应被移除。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WornCostumeComponent, "hero", _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(entity_manager)

        system._remove_costume(entity)

        assert not entity.has(WornCostumeComponent)

    def test_returns_item_to_storage(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: RemoveCostumeActionSystem,
    ) -> None:
        """脱下的时装道具应归还到储物箱。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WornCostumeComponent, "hero", _COSTUME)
        storage = _make_storage_entity(entity_manager)
        mock_game.get_storage_entity.return_value = storage

        system._remove_costume(entity)

        assert any(
            item.name == _COSTUME.name for item in storage.get(StorageComponent).items
        )

    def test_resets_appearance_to_base_body(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: RemoveCostumeActionSystem,
    ) -> None:
        """脱装后外观应重置为 base_body。"""
        entity = _make_actor_entity(entity_manager, "hero", appearance="穿着铁甲的战士")
        entity.add(WornCostumeComponent, "hero", _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(entity_manager)

        system._remove_costume(entity)

        assert entity.get(AppearanceComponent).appearance == _BASE_BODY

    def test_broadcasts_event(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: RemoveCostumeActionSystem,
    ) -> None:
        """脱装后应调用一次 broadcast_to_stage。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WornCostumeComponent, "hero", _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(entity_manager)

        system._remove_costume(entity)

        mock_game.broadcast_to_stage.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — react
# ---------------------------------------------------------------------------


class TestReact:
    """react() 的端到端单元测试。"""

    @pytest.mark.asyncio
    async def test_react_empty_entities(
        self, system: RemoveCostumeActionSystem
    ) -> None:
        """空实体列表时 react() 应正常完成，不抛出异常。"""
        await system.react([])

    @pytest.mark.asyncio
    async def test_react_removes_costume_end_to_end(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: RemoveCostumeActionSystem,
    ) -> None:
        """触发 RemoveCostumeAction 后，应脱装并归还储物箱、重置外观。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(RemoveCostumeAction, "hero")
        entity.add(WornCostumeComponent, "hero", _COSTUME)
        storage = _make_storage_entity(entity_manager)
        mock_game.get_storage_entity.return_value = storage

        await system.react([entity])

        assert not entity.has(WornCostumeComponent)
        assert entity.get(AppearanceComponent).appearance == _BASE_BODY
        assert any(
            item.name == _COSTUME.name for item in storage.get(StorageComponent).items
        )
