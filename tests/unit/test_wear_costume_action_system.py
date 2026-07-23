"""WearCostumeActionSystem 单元测试。"""

from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.ai_rpg.entitas import Entity
from src.ai_rpg.game.rpg_entity_manager import RPGEntityManager
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    AppearanceComponent,
    WornCostumeComponent,
    StorageComponent,
    WearCostumeAction,
)
from src.ai_rpg.models.items import CostumeItem
from src.ai_rpg.systems.wear_costume_action_system import (
    WearCostumeActionSystem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_BODY = "人类基础外形"
_COSTUME = CostumeItem(name="铁甲", description="坚固的铁制盔甲")
_NEW_COSTUME = CostumeItem(name="法袍", description="绣有星纹的深蓝色法袍")
_MODULE = "src.ai_rpg.systems.wear_costume_action_system"


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
def system(mock_game: MagicMock) -> WearCostumeActionSystem:
    return WearCostumeActionSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests — _process_wear_costume
# ---------------------------------------------------------------------------


class TestProcessWearCostume:
    """_process_wear_costume() 的单元测试。"""

    @pytest.mark.asyncio
    async def test_removes_costume_from_storage(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: WearCostumeActionSystem,
    ) -> None:
        """穿装后该时装应从储物箱中移除。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WearCostumeAction, "hero", _COSTUME.name, _COSTUME)
        storage = _make_storage_entity(entity_manager, [_COSTUME])
        mock_game.get_storage_entity.return_value = storage

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "合成外观"
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        assert all(
            item.name != _COSTUME.name for item in storage.get(StorageComponent).items
        )

    @pytest.mark.asyncio
    async def test_mounts_costume_component(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: WearCostumeActionSystem,
    ) -> None:
        """穿装后实体应持有 WornCostumeComponent，且 item 为指定时装。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WearCostumeAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "合成外观"
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        assert entity.has(WornCostumeComponent)
        assert entity.get(WornCostumeComponent).item.name == _COSTUME.name

    @pytest.mark.asyncio
    async def test_updates_appearance_from_llm(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: WearCostumeActionSystem,
    ) -> None:
        """LLM 返回非空内容时，外观应更新为 LLM 响应（去除首尾空白）。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WearCostumeAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "  穿着铁甲的英勇战士  "
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        assert entity.get(AppearanceComponent).appearance == "穿着铁甲的英勇战士"

    @pytest.mark.asyncio
    async def test_empty_llm_response_results_in_empty_appearance(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: WearCostumeActionSystem,
    ) -> None:
        """LLM 返回空字符串时，无兜底逻辑，外观直接更新为空字符串。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WearCostumeAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = ""
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        assert entity.get(AppearanceComponent).appearance == ""

    @pytest.mark.asyncio
    async def test_broadcasts_event(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: WearCostumeActionSystem,
    ) -> None:
        """穿装后应调用一次 broadcast_to_stage。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WearCostumeAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "合成外观"
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        mock_game.broadcast_to_stage.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_swaps_previously_worn_costume(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: WearCostumeActionSystem,
    ) -> None:
        """已穿戴时装时再穿新装，应自动先脱下旧时装归还储物箱，再穿上新时装。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WornCostumeComponent, "hero", _COSTUME)
        entity.add(WearCostumeAction, "hero", _NEW_COSTUME.name, _NEW_COSTUME)
        storage = _make_storage_entity(entity_manager, [_NEW_COSTUME])
        mock_game.get_storage_entity.return_value = storage

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "合成外观"
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        assert entity.get(WornCostumeComponent).item.name == _NEW_COSTUME.name
        storage_items = storage.get(StorageComponent).items
        assert any(item.name == _COSTUME.name for item in storage_items)
        assert all(item.name != _NEW_COSTUME.name for item in storage_items)
        # 换装（从有到更换）应只广播一次最终外观，不应有脱下旧装的中间态广播
        mock_game.broadcast_to_stage.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — react
# ---------------------------------------------------------------------------


class TestReact:
    """react() 的端到端单元测试。"""

    @pytest.mark.asyncio
    async def test_react_empty_entities(self, system: WearCostumeActionSystem) -> None:
        """空实体列表时 react() 应正常完成，不抛出异常。"""
        await system.react([])

    @pytest.mark.asyncio
    async def test_react_wears_new_costume_end_to_end(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: WearCostumeActionSystem,
    ) -> None:
        """触发 WearCostumeAction 后，应完成完整穿装流程并更新外观。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(WearCostumeAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "LLM合成外观"
            MockClient.return_value = mock_client
            await system.react([entity])

        assert entity.has(WornCostumeComponent)
        assert entity.get(AppearanceComponent).appearance == "LLM合成外观"
