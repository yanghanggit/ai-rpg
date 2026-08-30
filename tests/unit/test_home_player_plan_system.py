"""HomePlayerPlanSystem 单元测试。

聚焦三个关键环节，不追求覆盖度：
1. filter() 与 HomeNpcPlanSystem 的路由互斥（只处理玩家自身）
2. _extract_action_from_components()：由玩家已挂载的 Action 组件反推出 submit_action_plan 参数
3. _inject_player_mimic_messages()：确认全程不调用 LLM；伪造与 NPC 等价的工具调用轨迹写入记忆
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    NPCComponent,
    PlanAction,
    PlayerComponent,
    SpeakAction,
    StageDescriptionComponent,
)
from src.ai_rpg.systems.home_player_plan_system import HomePlayerPlanSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(context: Context, name: str = "角色.玩家A") -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.石台广场")
    entity.add(NPCComponent, name)
    entity.add(PlayerComponent, "player1")
    entity.add(PlanAction, name)
    return entity


def _make_npc(context: Context, name: str = "角色.NPC_A") -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.石台广场")
    entity.add(NPCComponent, name)
    entity.add(PlanAction, name)
    return entity


def _stub_scene(context: Context, mock_game: MagicMock) -> None:
    stage = context.create_entity()
    stage._name = "场景.石台广场"
    stage.add(StageDescriptionComponent, stage.name, "石台广场")
    mock_game.resolve_stage_entity.return_value = stage
    mock_game.get_actors_in_stage.return_value = set()
    mock_game.get_group.return_value.entities.copy.return_value = set()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    return MagicMock(spec=DBGGame)


@pytest.fixture()
def system(mock_game: MagicMock) -> HomePlayerPlanSystem:
    return HomePlayerPlanSystem(mock_game)


# ---------------------------------------------------------------------------
# filter()
# ---------------------------------------------------------------------------


class TestFilter:
    def test_accepts_player_entity(
        self, context: Context, system: HomePlayerPlanSystem
    ) -> None:
        """玩家实体必须同时挂载至少一种主动行动组件（如 SpeakAction）才会被接受。"""
        entity = _make_player(context)
        entity.replace(SpeakAction, entity.name, {"角色.NPC_A": "你好"})
        assert system.filter(entity) is True

    def test_rejects_player_entity_without_active_action(
        self, context: Context, system: HomePlayerPlanSystem
    ) -> None:
        """玩家实体虽持有 PlanAction，但未挂载任何主动行动组件时应被排除。"""
        assert system.filter(_make_player(context)) is False

    def test_rejects_plain_npc(
        self, context: Context, system: HomePlayerPlanSystem
    ) -> None:
        """不持有 PlayerComponent 的普通 NPC 必须被排除，交由 HomeNpcPlanSystem 处理。"""
        assert system.filter(_make_npc(context)) is False


# ---------------------------------------------------------------------------
# _extract_action_from_components — 玩家动作组件 → submit_action_plan 参数
# ---------------------------------------------------------------------------


class TestExtractActionFromComponents:
    def test_speak_action_is_extracted(
        self, context: Context, system: HomePlayerPlanSystem
    ) -> None:
        entity = _make_player(context)
        entity.replace(SpeakAction, entity.name, {"角色.NPC_A": "你好"})

        action_type, target_messages, message, target_stage_name = (
            system._extract_action_from_components(entity)
        )

        assert action_type == "speak"
        assert target_messages == {"角色.NPC_A": "你好"}
        assert message == ""
        assert target_stage_name == ""

    def test_no_action_returns_none_and_logs_warning(
        self, context: Context, system: HomePlayerPlanSystem
    ) -> None:
        """玩家没有任何主动动作组件（不应发生的非法状态）：返回 none 并记录警告。"""
        entity = _make_player(context)

        with patch(
            "src.ai_rpg.systems.home_player_plan_system.logger.warning"
        ) as mock_warning:
            action_type, target_messages, message, target_stage_name = (
                system._extract_action_from_components(entity)
            )

        assert action_type == "none"
        assert target_messages == {}
        assert message == ""
        assert target_stage_name == ""
        mock_warning.assert_called_once()


# ---------------------------------------------------------------------------
# _inject_player_mimic_messages — 端到端：不调用 LLM，伪造工具调用轨迹
# ---------------------------------------------------------------------------


class TestInjectPlayerMimicMessages:
    def test_active_speak_action_writes_mimic_tool_call(
        self, context: Context, mock_game: MagicMock, system: HomePlayerPlanSystem
    ) -> None:
        _stub_scene(context, mock_game)
        entity = _make_player(context)
        entity.replace(SpeakAction, entity.name, {"角色.NPC_A": "你好"})

        memory = MagicMock()
        memory.messages = []
        mock_game.get_agent_memory.return_value = memory

        system._inject_player_mimic_messages(entity)

        assert len(memory.messages) == 3
        human_msg, ai_msg, tool_msg = memory.messages

        assert human_msg.type == "human"
        assert ai_msg.type == "ai"
        assert ai_msg.content == ""  # tool call 的 AI 消息 content 为空

        tool_calls = ai_msg.additional_kwargs["tool_calls"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "submit_action_plan"
        args = json.loads(tool_calls[0]["function"]["arguments"])
        assert args["action_type"] == "speak"
        assert args["target_messages"] == {"角色.NPC_A": "你好"}
        assert args["mind"] == ""

        assert tool_msg.type == "tool"
        assert tool_msg.tool_call_id == tool_calls[0]["id"]

        mock_game.notify_entities.assert_not_called()
