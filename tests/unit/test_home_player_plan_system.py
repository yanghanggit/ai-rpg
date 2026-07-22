"""HomePlayerPlanSystem 单元测试。

聚焦三个关键环节，不追求覆盖度：
1. filter() 与 HomeNpcPlanSystem 的路由互斥（只处理玩家自身）
2. _build_player_action_response()：由玩家已挂载的 Action 组件反推出的"影子 plan"核心映射逻辑；
   若无任何主动行动组件（不应发生），返回 None 并记录警告，不再伪造"待命"占位内容
3. _inject_player_scene_context()：确认全程不调用 LLM；正常情况下写入与 NPC 真实 plan 同构的
   JSON 上下文，非法状态下（无主动行动）整体跳过、不写入任何消息
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


def _make_player(context: Context, name: str = "旅行者.无名氏") -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "wanderer", "场景.石台广场")
    entity.add(NPCComponent, name)
    entity.add(PlayerComponent, "player1")
    entity.add(PlanAction, name)
    return entity


def _make_npc(context: Context, name: str = "学者.寒蝉") -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "scholar", "场景.石台广场")
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
        entity.replace(SpeakAction, entity.name, {"学者.寒蝉": "你好"})
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
# _build_player_action_response — 影子 plan 的核心映射逻辑
# ---------------------------------------------------------------------------


class TestBuildPlayerActionResponse:
    def test_active_action_present_leaves_mind_empty(
        self, context: Context, system: HomePlayerPlanSystem
    ) -> None:
        """玩家本轮已由 API 挂载 SpeakAction：影子 plan 应还原该动作，mind 留空。"""
        entity = _make_player(context)
        entity.replace(SpeakAction, entity.name, {"学者.寒蝉": "你好"})

        response = system._build_player_action_response(entity)

        assert response is not None
        assert response.speak == {"学者.寒蝉": "你好"}
        assert response.mind == ""

    def test_no_action_returns_none_and_logs_warning(
        self, context: Context, system: HomePlayerPlanSystem
    ) -> None:
        """玩家没有任何主动动作组件（不应发生的非法状态）：返回 None 并记录警告，
        不再伪造"待命"占位内容。"""
        entity = _make_player(context)

        with patch(
            "src.ai_rpg.systems.home_player_plan_system.logger.warning"
        ) as mock_warning:
            response = system._build_player_action_response(entity)

        assert response is None
        mock_warning.assert_called_once()


# ---------------------------------------------------------------------------
# _inject_player_scene_context — 端到端：不调用 LLM，仅写入结构化上下文
# ---------------------------------------------------------------------------


class TestInjectPlayerSceneContext:
    def test_active_speak_action_writes_shadow_plan(
        self, context: Context, mock_game: MagicMock, system: HomePlayerPlanSystem
    ) -> None:
        _stub_scene(context, mock_game)
        entity = _make_player(context)
        entity.replace(SpeakAction, entity.name, {"学者.寒蝉": "你好"})

        system._inject_player_scene_context(entity)

        ai_message = mock_game.add_ai_message.call_args.args[1]
        payload = json.loads(ai_message.content)
        assert payload["speak"] == {"学者.寒蝉": "你好"}
        assert payload["mind"] == ""
        mock_game.notify_entities.assert_not_called()  # 本系统不再产生 MindEvent 通知
