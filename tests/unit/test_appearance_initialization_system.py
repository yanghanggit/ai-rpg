"""AppearanceInitializationSystem 单元测试。"""

from typing import List
from unittest.mock import MagicMock, patch
import pytest
from src.ai_rpg.deepseek import DeepSeekClient
from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    AppearanceComponent,
    WornCostumeComponent,
)
from src.ai_rpg.models.items import CostumeItem
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.systems.appearance_initialization_system import (
    AppearanceInitializationSystem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_BODY = "人类基础外形"
_COSTUME = CostumeItem(name="铁甲", description="坚固的铁制盔甲")


def _make_actor_entity(
    context: Context,
    name: str,
    appearance: str,
    costume: CostumeItem = _COSTUME,
) -> Entity:
    """创建一个带有 Actor、Appearance、Costume 组件的实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "test_sheet", "test_stage")
    entity.add(AppearanceComponent, name, _BASE_BODY, appearance)
    entity.add(WornCostumeComponent, name, costume)
    return entity


def _make_mock_chat_client(name: str, response_content: str) -> MagicMock:
    """构建一个模拟 LLM 已响应的 DeepSeekClient。"""
    client = MagicMock()
    client.name = name
    client.response_content = response_content
    client.response_ai_message = AIMessage(content=response_content)
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_agent_context.return_value = MagicMock(context=[])
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> AppearanceInitializationSystem:
    return AppearanceInitializationSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests — _build_client
# ---------------------------------------------------------------------------


class TestBuildClient:
    """_build_client() 的单元测试。"""

    def test_prompt_contains_base_body_and_costume_info(
        self, context: Context, system: AppearanceInitializationSystem
    ) -> None:
        """生成的 prompt 应包含基础体型与时装名称、描述；client.name 应与实体名一致。"""
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)

        client = system._build_client(entity)

        assert client.name == "英雄"
        assert _BASE_BODY in client.prompt
        assert _COSTUME.name in client.prompt
        assert _COSTUME.description in client.prompt


# ---------------------------------------------------------------------------
# Tests — _apply_result
# ---------------------------------------------------------------------------


class TestApplyResult:
    """_apply_result() 的单元测试。"""

    def test_updates_appearance_with_stripped_response(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AppearanceInitializationSystem,
    ) -> None:
        """LLM 响应应去除首尾空白后写入 AppearanceComponent.appearance。"""
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_entity_by_name.return_value = entity
        client = _make_mock_chat_client("英雄", "  穿着铁甲的战士  ")

        system._apply_result(client)

        assert entity.get(AppearanceComponent).appearance == "穿着铁甲的战士"

    def test_adds_wear_costume_message(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AppearanceInitializationSystem,
    ) -> None:
        """应调用一次 add_human_message，且内容包含角色名、时装名与新外观。"""
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_entity_by_name.return_value = entity
        client = _make_mock_chat_client("英雄", "穿着铁甲的战士")

        system._apply_result(client)

        mock_game.add_human_message.assert_called_once()
        message = mock_game.add_human_message.call_args[0][1]
        assert "英雄" in message.content
        assert _COSTUME.name in message.content
        assert "穿着铁甲的战士" in message.content

    def test_skips_when_response_ai_message_is_none(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AppearanceInitializationSystem,
    ) -> None:
        """LLM 未返回消息时，不更新外观，也不写入对话历史。"""
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_entity_by_name.return_value = entity
        client = MagicMock()
        client.name = "英雄"
        client.response_ai_message = None

        system._apply_result(client)

        assert entity.get(AppearanceComponent).appearance == _BASE_BODY
        mock_game.add_human_message.assert_not_called()


# ---------------------------------------------------------------------------
# Tests — execute
# ---------------------------------------------------------------------------


class TestExecute:
    """execute() 的端到端单元测试。"""

    @pytest.mark.asyncio
    async def test_only_uninitialized_actors_sent_to_batch_chat(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AppearanceInitializationSystem,
    ) -> None:
        """appearance == base_body 的角色应被送入 batch_chat；已初始化的角色应被排除。"""
        target = _make_actor_entity(context, "英雄", _BASE_BODY)
        initialized = _make_actor_entity(context, "法师", "已合成的法师外观")
        mock_game.get_group.return_value = MagicMock(entities=[target, initialized])

        with patch(
            "src.ai_rpg.systems.appearance_initialization_system.DeepSeekClient.batch_chat",
        ) as mock_batch:
            await system.execute()

        sent_names = {client.name for client in mock_batch.call_args[0][0]}
        assert sent_names == {"英雄"}

    @pytest.mark.asyncio
    async def test_execute_updates_appearance_end_to_end(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AppearanceInitializationSystem,
    ) -> None:
        """端到端：批量响应后，未初始化角色外观应更新，已初始化角色保持不变。"""
        target = _make_actor_entity(context, "英雄", _BASE_BODY)
        initialized = _make_actor_entity(context, "法师", "已合成的法师外观")
        mock_game.get_group.return_value = MagicMock(entities=[target, initialized])
        mock_game.get_entity_by_name.side_effect = lambda name: {
            "英雄": target,
            "法师": initialized,
        }.get(name)

        async def fake_batch_chat(clients: List[DeepSeekClient]) -> None:
            for client in clients:
                client._response_ai_message = AIMessage(content="穿着铁甲的战士")

        with patch(
            "src.ai_rpg.systems.appearance_initialization_system.DeepSeekClient.batch_chat",
            side_effect=fake_batch_chat,
        ):
            await system.execute()

        assert target.get(AppearanceComponent).appearance == "穿着铁甲的战士"
        assert initialized.get(AppearanceComponent).appearance == "已合成的法师外观"
