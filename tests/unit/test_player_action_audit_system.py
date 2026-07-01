"""PlayerActionAuditSystem 单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models.actions import AnnounceAction, SpeakAction, WhisperAction
from src.ai_rpg.models.components import (
    PlayerActionAuditComponent,
    PlayerComponent,
    WorldComponent,
)
from src.ai_rpg.models.messages import SystemMessage
from src.ai_rpg.models.world import AgentContext
from src.ai_rpg.systems.player_action_audit_system import (
    ContentAuditResponse,
    PlayerActionAuditSystem,
    _build_audit_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SPEAK_ARGS = ("player", {"bob": "你好"})
_WHISPER_ARGS = ("player", {"bob": "悄悄话"})
_ANNOUNCE_ARGS = ("player", "公告内容")


def _approved_json() -> str:
    return '{"is_approved": true, "reason": ""}'


def _rejected_json(reason: str = "内容违规") -> str:
    return f'{{"is_approved": false, "reason": "{reason}"}}'


def _make_agent_context(name: str = "audit_system") -> AgentContext:
    """构造包含 SystemMessage 的 AgentContext，满足系统内部 assert 条件。"""
    return AgentContext(
        name=name,
        context=[SystemMessage(content="你是内容审核员。")],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game(context: Context) -> MagicMock:
    """MagicMock DBGGame，将 get_group() 代理到真实 Context。"""
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = context.get_group
    game.get_agent_context.return_value = _make_agent_context()
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> PlayerActionAuditSystem:
    return PlayerActionAuditSystem(mock_game)


# ---------------------------------------------------------------------------
# Phase 1 — ContentAuditResponse 模型测试
# ---------------------------------------------------------------------------


class TestContentAuditResponse:
    def test_approved_with_empty_reason(self) -> None:
        r = ContentAuditResponse(is_approved=True)
        assert r.is_approved is True
        assert r.reason == ""

    def test_rejected_with_reason_string(self) -> None:
        r = ContentAuditResponse(is_approved=False, reason="含违禁词")
        assert r.is_approved is False
        assert r.reason == "含违禁词"

    def test_null_reason_coerced_to_empty_string(self) -> None:
        """AI 返回 null reason 时应自动转换为空字符串，不抛出验证错误。"""
        r = ContentAuditResponse.model_validate({"is_approved": True, "reason": None})
        assert r.reason == ""

    def test_missing_reason_defaults_to_empty_string(self) -> None:
        r = ContentAuditResponse.model_validate({"is_approved": False})
        assert r.reason == ""


# ---------------------------------------------------------------------------
# Phase 1 — _build_audit_prompt 测试
# ---------------------------------------------------------------------------


class TestBuildAuditPrompt:
    def test_content_appears_in_prompt(self) -> None:
        prompt = _build_audit_prompt("这是测试内容")
        assert "这是测试内容" in prompt

    def test_json_block_present(self) -> None:
        prompt = _build_audit_prompt("content")
        assert "```json" in prompt
        assert "is_approved" in prompt

    def test_output_format_fields_present(self) -> None:
        prompt = _build_audit_prompt("content")
        assert "reason" in prompt


# ---------------------------------------------------------------------------
# Phase 2 — _extract_all_action_contents 测试
# ---------------------------------------------------------------------------


class TestExtractAllActionContents:
    def test_only_speak_action(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        entity.add(SpeakAction, *_SPEAK_ARGS)
        result = system._extract_all_action_contents(entity)
        assert "【说话】" in result
        assert "【私聊】" not in result
        assert "【公告】" not in result

    def test_only_whisper_action(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        entity.add(WhisperAction, *_WHISPER_ARGS)
        result = system._extract_all_action_contents(entity)
        assert "【私聊】" in result
        assert "【说话】" not in result
        assert "【公告】" not in result

    def test_only_announce_action(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        entity.add(AnnounceAction, *_ANNOUNCE_ARGS)
        result = system._extract_all_action_contents(entity)
        assert "【公告】" in result
        assert "公告内容" in result

    def test_all_three_actions_joined(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        entity.add(SpeakAction, *_SPEAK_ARGS)
        entity.add(WhisperAction, *_WHISPER_ARGS)
        entity.add(AnnounceAction, *_ANNOUNCE_ARGS)
        result = system._extract_all_action_contents(entity)
        assert "【说话】" in result
        assert "【私聊】" in result
        assert "【公告】" in result
        assert "\n\n" in result

    def test_speak_content_included(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        entity.add(SpeakAction, "player", {"alice": "你好"})
        result = system._extract_all_action_contents(entity)
        assert "alice" in result
        assert "你好" in result

    def test_no_actions_returns_empty_string(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        result = system._extract_all_action_contents(entity)
        assert result == ""


# ---------------------------------------------------------------------------
# Phase 2 — _remove_all_actions 测试
# ---------------------------------------------------------------------------


class TestRemoveAllActions:
    def test_removes_all_three_actions(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        entity.add(SpeakAction, *_SPEAK_ARGS)
        entity.add(WhisperAction, *_WHISPER_ARGS)
        entity.add(AnnounceAction, *_ANNOUNCE_ARGS)

        system._remove_all_actions(entity)

        assert not entity.has(SpeakAction)
        assert not entity.has(WhisperAction)
        assert not entity.has(AnnounceAction)

    def test_removes_partial_actions_without_error(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        entity.add(SpeakAction, *_SPEAK_ARGS)
        # WhisperAction 和 AnnounceAction 故意不添加

        system._remove_all_actions(entity)  # 不应抛出异常

        assert not entity.has(SpeakAction)

    def test_no_actions_does_not_raise(
        self, context: Context, system: PlayerActionAuditSystem
    ) -> None:
        entity = context.create_entity()
        system._remove_all_actions(entity)  # 无动作，不应抛出


# ---------------------------------------------------------------------------
# Phase 3 — _filter_player_actions 异步测试
# ---------------------------------------------------------------------------


class TestFilterPlayerActions:
    def _make_audit_entity(self, context: Context) -> Entity:
        """创建带有审计组件的世界系统实体。"""
        entity = context.create_entity()
        entity._name = "世界系统.玩家行动审计系统"
        entity.add(WorldComponent, "世界系统.玩家行动审计系统")
        entity.add(PlayerActionAuditComponent, "世界系统.玩家行动审计系统")
        return entity

    def _make_player_entity(self, context: Context) -> Entity:
        entity = context.create_entity()
        entity._name = "玩家"
        entity.add(PlayerComponent, "玩家")
        return entity

    @pytest.mark.asyncio
    async def test_approved_preserves_actions(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PlayerActionAuditSystem,
    ) -> None:
        """AI 审核通过时，动作组件应保留在实体上。"""
        player = self._make_player_entity(context)
        player.add(SpeakAction, *_SPEAK_ARGS)
        world = self._make_audit_entity(context)

        with patch(
            "src.ai_rpg.systems.player_action_audit_system.DeepSeekClient"
        ) as MockClient:
            MockClient.return_value.response_content = _approved_json()
            MockClient.batch_chat = AsyncMock()

            await system._filter_player_actions(player, world)

        assert player.has(SpeakAction)

    @pytest.mark.asyncio
    async def test_rejected_removes_all_actions(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PlayerActionAuditSystem,
    ) -> None:
        """AI 审核拒绝时，所有动作组件应被移除。"""
        player = self._make_player_entity(context)
        player.add(SpeakAction, *_SPEAK_ARGS)
        player.add(AnnounceAction, *_ANNOUNCE_ARGS)
        world = self._make_audit_entity(context)

        with patch(
            "src.ai_rpg.systems.player_action_audit_system.DeepSeekClient"
        ) as MockClient:
            MockClient.return_value.response_content = _rejected_json()
            MockClient.batch_chat = AsyncMock()

            await system._filter_player_actions(player, world)

        assert not player.has(SpeakAction)
        assert not player.has(AnnounceAction)

    @pytest.mark.asyncio
    async def test_batch_chat_exception_removes_actions(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PlayerActionAuditSystem,
    ) -> None:
        """batch_chat 抛出异常时，fail-safe 应移除所有动作组件。"""
        player = self._make_player_entity(context)
        player.add(SpeakAction, *_SPEAK_ARGS)
        world = self._make_audit_entity(context)

        with patch(
            "src.ai_rpg.systems.player_action_audit_system.DeepSeekClient"
        ) as MockClient:
            MockClient.batch_chat = AsyncMock(side_effect=RuntimeError("网络错误"))

            await system._filter_player_actions(player, world)

        assert not player.has(SpeakAction)

    @pytest.mark.asyncio
    async def test_malformed_json_response_removes_actions(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PlayerActionAuditSystem,
    ) -> None:
        """AI 返回无法解析的 JSON 时，fail-safe 应移除所有动作组件。"""
        player = self._make_player_entity(context)
        player.add(SpeakAction, *_SPEAK_ARGS)
        world = self._make_audit_entity(context)

        with patch(
            "src.ai_rpg.systems.player_action_audit_system.DeepSeekClient"
        ) as MockClient:
            MockClient.return_value.response_content = "这不是JSON"
            MockClient.batch_chat = AsyncMock()

            await system._filter_player_actions(player, world)

        assert not player.has(SpeakAction)

    @pytest.mark.asyncio
    async def test_no_content_returns_early_without_ai_call(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PlayerActionAuditSystem,
    ) -> None:
        """实体无任何动作组件时应提前返回，不触发 AI 调用。"""
        player = self._make_player_entity(context)
        world = self._make_audit_entity(context)

        with patch(
            "src.ai_rpg.systems.player_action_audit_system.DeepSeekClient"
        ) as MockClient:
            MockClient.batch_chat = AsyncMock()

            await system._filter_player_actions(player, world)

        MockClient.batch_chat.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 3 — react 测试
# ---------------------------------------------------------------------------


class TestReact:
    def _make_audit_entity(self, context: Context) -> Entity:
        entity = context.create_entity()
        entity._name = "世界系统.玩家行动审计系统"
        entity.add(WorldComponent, "世界系统.玩家行动审计系统")
        entity.add(PlayerActionAuditComponent, "世界系统.玩家行动审计系统")
        return entity

    def _make_player_entity(self, context: Context) -> Entity:
        entity = context.create_entity()
        entity._name = "玩家"
        entity.add(PlayerComponent, "玩家")
        entity.add(SpeakAction, *_SPEAK_ARGS)
        return entity

    @pytest.mark.asyncio
    async def test_no_audit_entity_logs_error_and_returns(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PlayerActionAuditSystem,
    ) -> None:
        """未找到审计系统实体时，应 log error 并直接返回，不调用 _filter_player_actions。"""
        player = self._make_player_entity(context)
        # 故意不创建 audit entity

        with patch.object(
            system, "_filter_player_actions", new_callable=AsyncMock
        ) as mock_filter:
            await system.react([player])

        mock_filter.assert_not_called()

    @pytest.mark.asyncio
    async def test_react_delegates_to_filter_player_actions(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PlayerActionAuditSystem,
    ) -> None:
        """正常路径下，react 应委托给 _filter_player_actions 处理玩家实体。"""
        player = self._make_player_entity(context)
        self._make_audit_entity(context)

        with patch.object(
            system, "_filter_player_actions", new_callable=AsyncMock
        ) as mock_filter:
            await system.react([player])

        mock_filter.assert_called_once()
        call_args = mock_filter.call_args[0]
        assert call_args[0] is player
