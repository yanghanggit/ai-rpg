"""HomeNpcPlanSystem 单元测试。

聚焦三个关键环节，不追求覆盖度：
1. filter() 与 HomePlayerPlanSystem 的路由互斥（玩家角色也持有 NPCComponent，必须被排除）
2. _apply_actor_action_response()：LLM 响应 JSON → ECS 行动组件的映射，及异常响应的容错
3. react()：client-driven 设计下，只为传入的实体各发起一次真实 LLM 请求（不再有 is_player_active 分支）
"""

from typing import List
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
    QueryAction,
    SpeakAction,
    StageDescriptionComponent,
    TransStageAction,
    WhisperAction,
)
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.systems.home_npc_plan_system import HomeNpcPlanSystem
from src.ai_rpg.systems.home_planning_utils import ActionPlanResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(
    context: Context,
    name: str = "学者.寒蝉",
    *,
    with_plan: bool = True,
    is_player: bool = False,
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "scholar", "场景.石台广场")
    entity.add(NPCComponent, name)
    if with_plan:
        entity.add(PlanAction, name)
    if is_player:
        entity.add(PlayerComponent, "player1")
    return entity


def _make_chat_client(name: str, response_json: str) -> MagicMock:
    client = MagicMock()
    client.name = name
    client.prompt = "prompt"
    client.compressed_prompt = "compressed"
    client.response_content = response_json
    client.response_ai_message = AIMessage(content=response_json)
    return client


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
def system(mock_game: MagicMock) -> HomeNpcPlanSystem:
    return HomeNpcPlanSystem(mock_game)


# ---------------------------------------------------------------------------
# filter()
# ---------------------------------------------------------------------------


class TestFilter:
    def test_accepts_plain_npc(
        self, context: Context, system: HomeNpcPlanSystem
    ) -> None:
        assert system.filter(_make_actor(context)) is True

    def test_rejects_player_entity(
        self, context: Context, system: HomeNpcPlanSystem
    ) -> None:
        """玩家角色同样持有 NPCComponent，但必须被 NPC 系统排除，避免与
        HomePlayerPlanSystem 对同一实体重复触发。"""
        assert system.filter(_make_actor(context, is_player=True)) is False


# ---------------------------------------------------------------------------
# _apply_actor_action_response — LLM 响应 → ECS 行动组件映射
# ---------------------------------------------------------------------------


class TestApplyActorActionResponse:
    def test_speak_whisper_and_mind_are_mapped(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        entity = _make_actor(context)
        stage = context.create_entity()
        stage._name = "场景.石台广场"
        mock_game.resolve_stage_entity.return_value = stage

        response = ActionPlanResponse(
            mind="有点热",
            speak={"旅行者.无名氏": "你好"},
            whisper={"旅行者.无名氏": "悄悄话"},
        )
        system._apply_actor_action_response(entity, response)

        assert entity.get(SpeakAction).target_messages == {"旅行者.无名氏": "你好"}
        assert entity.get(WhisperAction).target_messages == {"旅行者.无名氏": "悄悄话"}
        mock_game.notify_entities.assert_called_once()
        notified_entities, event = mock_game.notify_entities.call_args.args
        assert notified_entities == {entity}
        assert event.content == "有点热"

    def test_query_and_trans_stage_are_mapped_without_mind_event(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        entity = _make_actor(context)
        response = ActionPlanResponse(
            mind="", query="沙漠历史", trans_stage="场景.断壁石室"
        )

        system._apply_actor_action_response(entity, response)

        assert entity.get(QueryAction).question == "沙漠历史"
        assert entity.get(TransStageAction).target_stage_name == "场景.断壁石室"
        mock_game.notify_entities.assert_not_called()  # mind 为空时不产生 MindEvent 通知


# ---------------------------------------------------------------------------
# _execute_actor_actions — 异常响应的容错
# ---------------------------------------------------------------------------


class TestExecuteActorActions:
    def test_invalid_json_response_is_ignored(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        entity = _make_actor(context)
        mock_game.get_entity_by_name.return_value = entity

        system._execute_actor_actions(_make_chat_client(entity.name, "不是JSON"))

        mock_game.add_human_message.assert_not_called()
        assert not entity.has(SpeakAction)

    def test_empty_ai_message_is_ignored(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        entity = _make_actor(context)
        mock_game.get_entity_by_name.return_value = entity
        client = _make_chat_client(entity.name, "{}")
        client.response_ai_message = None

        system._execute_actor_actions(client)

        mock_game.add_human_message.assert_not_called()


# ---------------------------------------------------------------------------
# react() — client-driven 分发：只为传入的实体各发起一次真实 plan 请求
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_dispatches_one_client_per_npc_and_injects_mock_context(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        """2 个 NPC 传入 → batch_chat 应收到 2 个 client（不再有 is_player_active
        分支跳过任何一个）；每个 NPC 均被注入临时的“禁止 trans_stage” mock 消息。"""
        stage = context.create_entity()
        stage._name = "场景.石台广场"
        stage.add(StageDescriptionComponent, stage.name, "石台广场")
        mock_game.resolve_stage_entity.return_value = stage
        mock_game.get_actors_in_stage.return_value = set()
        mock_game.get_group.return_value.entities.copy.return_value = set()
        mock_game.get_agent_context.return_value = MagicMock(context=[])

        npc1 = _make_actor(context, "学者.寒蝉")
        npc2 = _make_actor(context, "旅行者.无名氏")

        captured: List[object] = []

        async def _capture(clients: List[object]) -> None:
            captured.extend(clients)

        with (
            patch(
                "src.ai_rpg.systems.home_npc_plan_system.DeepSeekClient.batch_chat",
                side_effect=_capture,
            ),
            patch.object(system, "_execute_actor_actions"),
        ):
            await system.react([npc1, npc2])

        assert len(captured) == 2
        mock_messages = [
            call.args[1].content for call in mock_game.add_human_message.call_args_list
        ]
        assert len(mock_messages) == 2
        assert all("不可以使用trans_stage" in content for content in mock_messages)
