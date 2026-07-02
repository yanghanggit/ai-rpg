"""UpdateAppearanceActionSystem 单元测试。"""

from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.entitas import Entity
from src.ai_rpg.game.rpg_entity_manager import RPGEntityManager
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    AppearanceComponent,
    CostumeComponent,
    StorageComponent,
    UpdateAppearanceAction,
)
from src.ai_rpg.models.items import CostumeItem
from src.ai_rpg.systems.update_appearance_action_system import (
    UpdateAppearanceActionSystem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_BODY = "人类基础外形"
_COSTUME = CostumeItem(name="铁甲", description="坚固的铁制盔甲")
_MODULE = "src.ai_rpg.systems.update_appearance_action_system"


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
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> UpdateAppearanceActionSystem:
    return UpdateAppearanceActionSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests — _process_remove_costume
# ---------------------------------------------------------------------------


class TestProcessRemoveCostume:
    """_process_remove_costume() 的单元测试。"""

    def test_skips_when_no_costume(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """没有 CostumeComponent 的实体应静默跳过，不调用 broadcast_to_stage。"""
        entity = _make_actor_entity(entity_manager, "hero")

        system._process_remove_costume(entity)

        mock_game.broadcast_to_stage.assert_not_called()

    def test_removes_costume_component(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """有 CostumeComponent 时，执行后组件应被移除。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(CostumeComponent, "hero", _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(entity_manager)

        system._process_remove_costume(entity)

        assert not entity.has(CostumeComponent)

    def test_returns_item_to_storage(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """脱下的时装道具应归还到储物箱。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(CostumeComponent, "hero", _COSTUME)
        storage = _make_storage_entity(entity_manager)
        mock_game.get_storage_entity.return_value = storage

        system._process_remove_costume(entity)

        assert any(
            item.name == _COSTUME.name for item in storage.get(StorageComponent).items
        )

    def test_resets_appearance_to_base_body(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """脱装后外观应重置为 base_body。"""
        entity = _make_actor_entity(entity_manager, "hero", appearance="穿着铁甲的战士")
        entity.add(CostumeComponent, "hero", _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(entity_manager)

        system._process_remove_costume(entity)

        assert entity.get(AppearanceComponent).appearance == _BASE_BODY

    def test_broadcasts_event(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """脱装后应调用一次 broadcast_to_stage。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(CostumeComponent, "hero", _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(entity_manager)

        system._process_remove_costume(entity)

        mock_game.broadcast_to_stage.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — _process_wear_costume
# ---------------------------------------------------------------------------


class TestProcessWearCostume:
    """_process_wear_costume() 的单元测试。"""

    @pytest.mark.asyncio
    async def test_skips_when_costume_item_is_none(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """action.costume_item 为 None 时应静默跳过，不挂载组件也不广播。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(UpdateAppearanceAction, "hero", _COSTUME.name, None)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        await system._process_wear_costume(entity)

        assert not entity.has(CostumeComponent)
        mock_game.broadcast_to_stage.assert_not_called()

    @pytest.mark.asyncio
    async def test_removes_costume_from_storage(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """穿装后该时装应从储物箱中移除。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(UpdateAppearanceAction, "hero", _COSTUME.name, _COSTUME)
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
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """穿装后实体应持有 CostumeComponent，且 item 为指定时装。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(UpdateAppearanceAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "合成外观"
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        assert entity.has(CostumeComponent)
        assert entity.get(CostumeComponent).item.name == _COSTUME.name

    @pytest.mark.asyncio
    async def test_updates_appearance_from_llm(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """LLM 返回非空内容时，外观应更新为 LLM 响应（去除首尾空白）。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(UpdateAppearanceAction, "hero", _COSTUME.name, _COSTUME)
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
    async def test_fallback_on_empty_llm_response(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """LLM 返回空字符串时，外观应退回 base_body + costume.description 的拼接。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(UpdateAppearanceAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = ""
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        assert entity.get(AppearanceComponent).appearance == (
            f"{_BASE_BODY}，{_COSTUME.description}"
        )

    @pytest.mark.asyncio
    async def test_broadcasts_event(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """穿装后应调用一次 broadcast_to_stage。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(UpdateAppearanceAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "合成外观"
            MockClient.return_value = mock_client
            await system._process_wear_costume(entity)

        mock_game.broadcast_to_stage.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — react
# ---------------------------------------------------------------------------


class TestReact:
    """react() 的端到端单元测试。"""

    @pytest.mark.asyncio
    async def test_react_empty_entities(
        self, system: UpdateAppearanceActionSystem
    ) -> None:
        """空实体列表时 react() 应正常完成，不抛出异常。"""
        await system.react([])

    @pytest.mark.asyncio
    async def test_react_only_removes_when_no_new_costume(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """action.costume_item_name 为空时，应脱装但不穿新装。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(UpdateAppearanceAction, "hero", "", None)
        entity.add(CostumeComponent, "hero", _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(entity_manager)

        await system.react([entity])

        assert not entity.has(CostumeComponent)

    @pytest.mark.asyncio
    async def test_react_wears_new_costume_end_to_end(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: UpdateAppearanceActionSystem,
    ) -> None:
        """action.costume_item_name 非空时，应完成完整穿装流程并更新外观。"""
        entity = _make_actor_entity(entity_manager, "hero")
        entity.add(UpdateAppearanceAction, "hero", _COSTUME.name, _COSTUME)
        mock_game.get_storage_entity.return_value = _make_storage_entity(
            entity_manager, [_COSTUME]
        )

        with patch(f"{_MODULE}.DeepSeekClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.response_content = "LLM合成外观"
            MockClient.return_value = mock_client
            await system.react([entity])

        assert entity.has(CostumeComponent)
        assert entity.get(AppearanceComponent).appearance == "LLM合成外观"
