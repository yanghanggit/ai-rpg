"""`AppearanceSynthesisSystem` 单元测试（管道起点的外观补齐）。

核心不变量：推理只送「世界实体 system prompt + 任务提示词」，不读角色记忆；
结果写回 `AppearanceComponent` 并给本人一条自我状态说明，不做全场景广播。
共用部分（label / 世界实体 / 客户端构造）的测试见 `test_appearance_synthesis_common.py`。
"""

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from ai_rpg.deepseek import DeepSeekClient
from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    AIMessage,
    AppearanceComponent,
    AppearanceSynthesisComponent,
    CostumeItem,
    SystemMessage,
    WornCostumeComponent,
)
from ai_rpg.systems.appearance_synthesis_common import make_appearance_label
from ai_rpg.systems.appearance_synthesis_system import AppearanceSynthesisSystem

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_BODY = "人类基础外形"
_COSTUME = CostumeItem(name="铁甲", description="坚固的铁制盔甲")
_WORLD_SYSTEM_PROMPT = "你是外观合成器，只输出外观描述。"


def _make_actor_entity(
    context: Context,
    name: str,
    appearance: str,
    costume: CostumeItem = _COSTUME,
) -> Entity:
    """创建一个带有 Actor、Appearance、Costume 组件的实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "test_stage")
    entity.add(AppearanceComponent, name, _BASE_BODY, appearance)
    entity.add(WornCostumeComponent, name, costume)
    return entity


def _make_world_entity(context: Context) -> Entity:
    """创建一个带 AppearanceSynthesisComponent 的世界实体。"""
    entity = context.create_entity()
    entity._name = "世界.外观合成"
    entity.add(AppearanceSynthesisComponent, entity._name)
    return entity


def _make_mock_chat_client(name: str, response_content: str) -> MagicMock:
    """构建一个模拟 LLM 已响应的 DeepSeekClient（label 用真实复合格式）。"""
    client = MagicMock()
    client.label = make_appearance_label("世界.外观合成", name)
    client.response_content = response_content
    client.response_ai_message = AIMessage(content=response_content)
    return client


def _group_mock(entities: List[Entity]) -> MagicMock:
    """模拟 game.get_group(...).entities。"""
    return MagicMock(entities=entities)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_agent_memory.return_value = MagicMock(
        messages=[SystemMessage(content=_WORLD_SYSTEM_PROMPT)]
    )
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> AppearanceSynthesisSystem:
    return AppearanceSynthesisSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests — resolve_appearance_synthesis_entity
# ---------------------------------------------------------------------------


class TestApplyResult:
    def test_updates_appearance_with_stripped_response(
        self, context: Context, mock_game: MagicMock, system: AppearanceSynthesisSystem
    ) -> None:
        """LLM 响应应去除首尾空白后写入 AppearanceComponent.appearance。"""
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_entity_by_name.return_value = entity

        system._apply_result(_make_mock_chat_client("英雄", "  穿着铁甲的战士  "))

        assert entity.get(AppearanceComponent).appearance == "穿着铁甲的战士"

    def test_writes_only_self_state_message(
        self, context: Context, mock_game: MagicMock, system: AppearanceSynthesisSystem
    ) -> None:
        """推理不留痕，但本人要收到一条自我状态说明；不写 AI 消息（不留推理原文）。"""
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_entity_by_name.return_value = entity

        system._apply_result(_make_mock_chat_client("英雄", "穿着铁甲的战士"))

        mock_game.add_ai_message.assert_not_called()
        mock_game.add_human_message.assert_called_once()
        kwargs = mock_game.add_human_message.call_args.kwargs
        assert kwargs["entity"] is entity
        message = kwargs["human_message"]
        assert kwargs["human_message"].appearance_update == "self"
        assert message.content.startswith("# 你的外观")
        assert _COSTUME.name in message.content
        assert "穿着铁甲的战士" in message.content

    def test_skips_when_response_ai_message_is_none(
        self, context: Context, mock_game: MagicMock, system: AppearanceSynthesisSystem
    ) -> None:
        """LLM 未返回消息时，外观保持原状。"""
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_entity_by_name.return_value = entity
        client = MagicMock()
        client.label = "英雄"
        client.response_ai_message = None

        system._apply_result(client)

        assert entity.get(AppearanceComponent).appearance == _BASE_BODY

    def test_skips_when_response_empty(
        self, context: Context, mock_game: MagicMock, system: AppearanceSynthesisSystem
    ) -> None:
        """空文本不写回，避免把外观刷成空串。"""
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_entity_by_name.return_value = entity

        system._apply_result(_make_mock_chat_client("英雄", "   "))

        assert entity.get(AppearanceComponent).appearance == _BASE_BODY


# ---------------------------------------------------------------------------
# Tests — execute
# ---------------------------------------------------------------------------


class TestExecute:
    async def test_only_uninitialized_actors_sent_to_batch_chat(
        self, context: Context, mock_game: MagicMock, system: AppearanceSynthesisSystem
    ) -> None:
        """appearance == base_body 的角色应被送入 batch_chat；已合成的排除。"""
        world = _make_world_entity(context)
        target = _make_actor_entity(context, "英雄", _BASE_BODY)
        initialized = _make_actor_entity(context, "法师", "已合成的法师外观")
        # 两个 get_group 调用：先查角色（筛未合成），再查世界实体（AppearanceSynthesisComponent）
        mock_game.get_group.side_effect = [
            _group_mock([target, initialized]),
            _group_mock([world]),
        ]

        with patch(
            "ai_rpg.systems.appearance_synthesis_system.batch_chat",
        ) as mock_batch:
            await system.execute()

        # label 是「主体|服务对象」：批量请求按角色去重，主体恒为世界实体
        sent_labels = {client.label for client in mock_batch.call_args[0][0]}
        assert sent_labels == {"世界.外观合成|英雄"}

    async def test_execute_updates_appearance_end_to_end(
        self, context: Context, mock_game: MagicMock, system: AppearanceSynthesisSystem
    ) -> None:
        """端到端：合成后外观更新，已合成角色不变；只给本人一条自我状态说明。"""
        world = _make_world_entity(context)
        target = _make_actor_entity(context, "英雄", _BASE_BODY)
        initialized = _make_actor_entity(context, "法师", "已合成的法师外观")
        mock_game.get_group.side_effect = [
            _group_mock([target, initialized]),
            _group_mock([world]),
        ]
        mock_game.get_entity_by_name.side_effect = lambda name: {
            "英雄": target,
            "法师": initialized,
        }.get(name)

        async def fake_batch_chat(clients: List[DeepSeekClient]) -> None:
            for client in clients:
                client._response_ai_message = AIMessage(content="穿着铁甲的战士")

        with patch(
            "ai_rpg.systems.appearance_synthesis_system.batch_chat",
            side_effect=fake_batch_chat,
        ):
            await system.execute()

        assert target.get(AppearanceComponent).appearance == "穿着铁甲的战士"
        assert initialized.get(AppearanceComponent).appearance == "已合成的法师外观"

        # 只有被合成的角色收到一条自我状态说明；已合成者不受打扰；不写 AI 消息。
        mock_game.add_ai_message.assert_not_called()
        mock_game.add_human_message.assert_called_once()
        assert mock_game.add_human_message.call_args.kwargs["entity"] is target

    async def test_asserts_without_world_entity(
        self, context: Context, mock_game: MagicMock, system: AppearanceSynthesisSystem
    ) -> None:
        """世界实体缺失时直接断言（数据错误），不进入推理、不改外观。"""
        target = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_group.side_effect = [
            _group_mock([target]),
            _group_mock([]),
        ]

        with patch(
            "ai_rpg.systems.appearance_synthesis_system.batch_chat",
        ) as mock_batch:
            with pytest.raises(AssertionError, match="外观合成世界实体数量异常"):
                await system.execute()

        mock_batch.assert_not_called()
        assert target.get(AppearanceComponent).appearance == _BASE_BODY
