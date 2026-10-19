"""`appearance_synthesis_common` 单元测试（管道补合成与穿装共用的部分）。

核心不变量：两条路径共用同一个世界实体、同一套 label 格式与同一份隔离式客户端构造，
因此这里锁住 label 组合/解析、世界实体定位与「messages 只有世界实体 system prompt」。
"""

from typing import List
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    AppearanceComponent,
    AppearanceSynthesisComponent,
    CostumeItem,
    SystemMessage,
    WornCostumeComponent,
)
from ai_rpg.systems.appearance_synthesis_common import (
    build_appearance_synthesis_request,
    make_appearance_label,
    parse_appearance_label,
    resolve_appearance_synthesis_entity,
)

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


class TestResolveWorldEntity:
    def test_returns_unique_world_entity(self, context: Context) -> None:
        world = _make_world_entity(context)
        game = MagicMock(spec=DBGGame)
        game.get_group.return_value = _group_mock([world])

        assert resolve_appearance_synthesis_entity(game) is world

    def test_asserts_when_missing(self, context: Context) -> None:
        """蓝图缺少该世界实体属于数据错误：断言而不是静默跳过。"""
        game = MagicMock(spec=DBGGame)
        game.get_group.return_value = _group_mock([])

        with pytest.raises(AssertionError, match="外观合成世界实体数量异常"):
            resolve_appearance_synthesis_entity(game)

    def test_asserts_when_duplicated(self, context: Context) -> None:
        first = _make_world_entity(context)
        second = _make_world_entity(context)
        game = MagicMock(spec=DBGGame)
        game.get_group.return_value = _group_mock([first, second])

        with pytest.raises(AssertionError, match="外观合成世界实体数量异常"):
            resolve_appearance_synthesis_entity(game)


# ---------------------------------------------------------------------------
# Tests — label 组合与解析
# ---------------------------------------------------------------------------


class TestLabel:
    def test_round_trip(self) -> None:
        label = make_appearance_label("世界.外观合成", "角色.无名")
        assert label == "世界.外观合成|角色.无名"
        assert parse_appearance_label(label) == ("世界.外观合成", "角色.无名")

    def test_rejects_illegal_label(self) -> None:
        with pytest.raises(AssertionError):
            parse_appearance_label("角色.无名")


# ---------------------------------------------------------------------------
# Tests — build_appearance_synthesis_request
# ---------------------------------------------------------------------------


class TestBuildRequest:
    def test_prompt_contains_base_body_and_costume_info(
        self, context: Context, mock_game: MagicMock
    ) -> None:
        """任务提示词只带数据：基础体型 + 时装名与描述；label 与实体名一致。"""
        world = _make_world_entity(context)
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)

        request = build_appearance_synthesis_request(mock_game, world, entity)

        assert request.label == "世界.外观合成|英雄"
        assert _BASE_BODY in request.input_message
        assert _COSTUME.name in request.input_message
        assert _COSTUME.description in request.input_message

    def test_context_is_only_world_system_prompt(
        self, context: Context, mock_game: MagicMock
    ) -> None:
        """隔离记忆：随行消息只有世界实体的 system prompt 一条，不含角色记忆。"""
        world = _make_world_entity(context)
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)

        request = build_appearance_synthesis_request(mock_game, world, entity)

        assert len(request.messages) == 1
        assert isinstance(request.messages[0], SystemMessage)
        assert request.messages[0].content == _WORLD_SYSTEM_PROMPT
        # 角色记忆参与了构造过程吗？只允许读世界实体的记忆。
        mock_game.get_agent_memory.assert_called_once_with(world)

    def test_requires_world_system_message(
        self, context: Context, mock_game: MagicMock
    ) -> None:
        world = _make_world_entity(context)
        entity = _make_actor_entity(context, "英雄", _BASE_BODY)
        mock_game.get_agent_memory.return_value = MagicMock(messages=[])

        with pytest.raises(AssertionError):
            build_appearance_synthesis_request(mock_game, world, entity)


# ---------------------------------------------------------------------------
# Tests — _apply_result
# ---------------------------------------------------------------------------


class TestLabelBoundary:
    def test_rejects_separator_in_name(self) -> None:
        """实体名含分隔符会让回写解析崩掉，故拼装时直接断言。"""
        with pytest.raises(AssertionError):
            make_appearance_label("世界.外观合成", "角色|无名")
