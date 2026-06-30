"""ActorAppearanceInitSystem 单元测试。"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.deepseek import DeepSeekClient
from src.ai_rpg.entitas import Entity
from src.ai_rpg.game.rpg_entity_manager import RPGEntityManager
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import ActorComponent, AppearanceComponent, CostumeComponent
from src.ai_rpg.models.items import CostumeItem
from src.ai_rpg.systems.appearance_initialization_system import (
    AppearanceInitializationSystem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_BODY = "人类基础外形"
_COSTUME = CostumeItem(name="铁甲", description="坚固的铁制盔甲")


def _make_actor_entity(
    entity_manager: RPGEntityManager,
    name: str,
    appearance: str,
    costume: CostumeItem = _COSTUME,
) -> Entity:
    """创建一个带有 Actor、Appearance、Costume 组件的实体。"""
    entity = entity_manager._create_entity(name)
    entity.add(ActorComponent, name, "hero_sheet", "home")
    entity.add(AppearanceComponent, name, _BASE_BODY, appearance)
    entity.add(CostumeComponent, name, costume)
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
    """Mock TCGGame，代理 ECS 操作到真实 RPGEntityManager。"""
    game = MagicMock(spec=TCGGame)
    game.get_group.side_effect = entity_manager.get_group
    game.get_entity_by_name.side_effect = entity_manager.get_entity_by_name
    game.get_agent_context.return_value = MagicMock(context=[])
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> AppearanceInitializationSystem:
    return AppearanceInitializationSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests — _get_targets
# ---------------------------------------------------------------------------


class TestGetTargets:
    """_get_targets() 的单元测试。"""

    def test_empty_world_returns_empty(
        self, system: AppearanceInitializationSystem
    ) -> None:
        """无实体时应返回空列表。"""
        assert system._get_targets() == []

    def test_includes_uninitialized_actor(
        self, entity_manager: RPGEntityManager, system: AppearanceInitializationSystem
    ) -> None:
        """appearance == base_body 且穿戴时装的角色应被筛选出（未初始化）。"""
        _make_actor_entity(entity_manager, "hero", _BASE_BODY)

        targets = system._get_targets()

        assert len(targets) == 1
        assert targets[0].name == "hero"

    def test_excludes_initialized_actor(
        self, entity_manager: RPGEntityManager, system: AppearanceInitializationSystem
    ) -> None:
        """appearance != base_body 的角色不应被筛选出（已初始化）。"""
        _make_actor_entity(entity_manager, "hero", "穿着铁甲的勇士")

        targets = system._get_targets()

        assert targets == []

    def test_excludes_actor_without_costume(
        self, entity_manager: RPGEntityManager, system: AppearanceInitializationSystem
    ) -> None:
        """没有 CostumeComponent 的角色不应被筛选出。"""
        entity = entity_manager._create_entity("hero")
        entity.add(ActorComponent, "hero", "hero_sheet", "home")
        entity.add(AppearanceComponent, "hero", _BASE_BODY, _BASE_BODY)
        # 不添加 CostumeComponent

        targets = system._get_targets()

        assert targets == []

    def test_mixed_returns_only_uninitialized(
        self, entity_manager: RPGEntityManager, system: AppearanceInitializationSystem
    ) -> None:
        """多个角色中，只有未初始化的应被筛选出。"""
        _make_actor_entity(entity_manager, "hero_a", _BASE_BODY)
        _make_actor_entity(entity_manager, "hero_b", "已合成外观")

        targets = system._get_targets()

        assert len(targets) == 1
        assert targets[0].name == "hero_a"


# ---------------------------------------------------------------------------
# Tests — _build_clients
# ---------------------------------------------------------------------------


class TestBuildClients:
    """_build_clients() 的单元测试。"""

    def test_returns_empty_for_no_targets(
        self, system: AppearanceInitializationSystem
    ) -> None:
        """空列表输入应返回空列表。"""
        assert system._build_clients([]) == []

    def test_count_matches_targets(
        self, entity_manager: RPGEntityManager, system: AppearanceInitializationSystem
    ) -> None:
        """返回的 client 数量应与目标实体数量一致。"""
        targets = [
            _make_actor_entity(entity_manager, "hero_a", _BASE_BODY),
            _make_actor_entity(entity_manager, "hero_b", _BASE_BODY),
        ]

        clients = system._build_clients(targets)

        assert len(clients) == 2

    def test_client_names_match_entities(
        self, entity_manager: RPGEntityManager, system: AppearanceInitializationSystem
    ) -> None:
        """每个 client 的 name 应与对应实体的 name 一致。"""
        targets = [
            _make_actor_entity(entity_manager, "alice", _BASE_BODY),
            _make_actor_entity(entity_manager, "bob", _BASE_BODY),
        ]

        clients = system._build_clients(targets)

        assert {c.name for c in clients} == {"alice", "bob"}


# ---------------------------------------------------------------------------
# Tests — _apply_result
# ---------------------------------------------------------------------------


class TestApplyResult:
    """_apply_result() 的单元测试。"""

    def test_updates_appearance_with_llm_response(
        self,
        entity_manager: RPGEntityManager,
        system: AppearanceInitializationSystem,
    ) -> None:
        """LLM 返回非空内容时，AppearanceComponent.appearance 应被更新。"""
        _make_actor_entity(entity_manager, "hero", _BASE_BODY)

        client = MagicMock(spec=DeepSeekClient)
        client.name = "hero"
        client.response_content = "  穿着铁甲的英勇战士  "

        system._apply_result(client)

        entity = entity_manager.get_entity_by_name("hero")
        assert entity is not None
        assert entity.get(AppearanceComponent).appearance == "穿着铁甲的英勇战士"

    def test_fallback_on_empty_response(
        self,
        entity_manager: RPGEntityManager,
        system: AppearanceInitializationSystem,
    ) -> None:
        """LLM 返回空字符串时，应退回 base_body + costume.description 的拼接。"""
        _make_actor_entity(entity_manager, "hero", _BASE_BODY)

        client = MagicMock(spec=DeepSeekClient)
        client.name = "hero"
        client.response_content = ""

        system._apply_result(client)

        entity = entity_manager.get_entity_by_name("hero")
        assert entity is not None
        assert (
            entity.get(AppearanceComponent).appearance
            == f"{_BASE_BODY}，{_COSTUME.description}"
        )

    def test_calls_add_human_message(
        self,
        entity_manager: RPGEntityManager,
        mock_game: MagicMock,
        system: AppearanceInitializationSystem,
    ) -> None:
        """_apply_result() 执行后应调用一次 add_human_message。"""
        _make_actor_entity(entity_manager, "hero", _BASE_BODY)

        client = MagicMock(spec=DeepSeekClient)
        client.name = "hero"
        client.response_content = "穿着铁甲的战士"

        system._apply_result(client)

        mock_game.add_human_message.assert_called_once()


# ---------------------------------------------------------------------------
# Tests — execute
# ---------------------------------------------------------------------------


class TestExecute:
    """execute() 的端到端单元测试。"""

    @pytest.mark.asyncio
    async def test_execute_empty_world_skips_batch_chat(
        self, system: AppearanceInitializationSystem
    ) -> None:
        """无实体时不应调用 DeepSeekClient.batch_chat。"""
        with patch.object(
            DeepSeekClient, "batch_chat", new_callable=AsyncMock
        ) as mock_batch:
            await system.execute()
            mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_skips_when_all_initialized(
        self,
        entity_manager: RPGEntityManager,
        system: AppearanceInitializationSystem,
    ) -> None:
        """所有角色外观已初始化时不应调用 batch_chat。"""
        _make_actor_entity(entity_manager, "hero", "已初始化的外观")

        with patch.object(
            DeepSeekClient, "batch_chat", new_callable=AsyncMock
        ) as mock_batch:
            await system.execute()
            mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_calls_batch_chat_for_uninitialized(
        self,
        entity_manager: RPGEntityManager,
        system: AppearanceInitializationSystem,
    ) -> None:
        """存在未初始化角色时应调用 batch_chat。"""
        _make_actor_entity(entity_manager, "hero", _BASE_BODY)

        with patch.object(
            DeepSeekClient, "batch_chat", new_callable=AsyncMock
        ) as mock_batch:
            await system.execute()
            mock_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_updates_appearance_end_to_end(
        self,
        entity_manager: RPGEntityManager,
        system: AppearanceInitializationSystem,
    ) -> None:
        """端到端：执行后角色外观应更新为 LLM 返回的内容。"""
        _make_actor_entity(entity_manager, "hero", _BASE_BODY)

        async def fake_batch_chat(clients: List[DeepSeekClient]) -> None:
            for client in clients:
                client._response_ai_message = MagicMock(content="LLM合成的外观")

        with patch.object(DeepSeekClient, "batch_chat", side_effect=fake_batch_chat):
            await system.execute()

        entity = entity_manager.get_entity_by_name("hero")
        assert entity is not None
        assert entity.get(AppearanceComponent).appearance == "LLM合成的外观"
