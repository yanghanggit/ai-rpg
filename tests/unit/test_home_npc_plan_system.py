"""HomeNpcPlanSystem 单元测试。

聚焦三个关键环节，不追求覆盖度：
1. filter() 与 HomePlayerPlanSystem 的路由互斥（玩家角色也持有 NPCComponent，必须被排除）
2. _apply_submitted_action()：提交结果 → ECS 行动组件的映射，及空 payload 的容错
3. react()：client-driven 设计下，只为传入的实体各发起一次 agent_loop 规划
"""

from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

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
    TransStageAction,
    WhisperAction,
)
from src.ai_rpg.systems.home_npc_plan_system import HomeNpcPlanSystem
from src.ai_rpg.systems.home_planning import PlanResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(
    context: Context,
    name: str = "角色.NPC_A",
    *,
    with_plan: bool = True,
    is_player: bool = False,
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.石台广场")
    entity.add(NPCComponent, name)
    if with_plan:
        entity.add(PlanAction, name)
    if is_player:
        entity.add(PlayerComponent, "player1")
    return entity


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
# _apply_submitted_action — 提交结果 → ECS 行动组件映射
# ---------------------------------------------------------------------------


class TestApplySubmittedAction:
    def test_speak_and_mind_are_mapped(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        entity = _make_actor(context)
        stage = context.create_entity()
        stage._name = "场景.石台广场"
        mock_game.resolve_stage_entity.return_value = stage

        result = PlanResult(
            submitted=True,
            mind="有点热",
            action_type="speak",
            target_messages={"角色.玩家A": "你好"},
        )
        system._apply_submitted_action(entity, result)

        assert entity.get(SpeakAction).target_messages == {"角色.玩家A": "你好"}
        mock_game.notify_entities.assert_called_once()
        notified_entities, event = mock_game.notify_entities.call_args.args
        assert notified_entities == {entity}
        assert event.content == "有点热"

    def test_trans_stage_without_mind_event(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        entity = _make_actor(context)

        result = PlanResult(
            submitted=True,
            mind="",
            action_type="trans_stage",
            target_stage_name="场景.断壁石室",
        )
        system._apply_submitted_action(entity, result)

        assert entity.get(TransStageAction).target_stage_name == "场景.断壁石室"
        mock_game.notify_entities.assert_not_called()

    def test_none_action_mounts_nothing(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        entity = _make_actor(context)

        result = PlanResult(submitted=True, mind="", action_type="none")
        system._apply_submitted_action(entity, result)

        assert not entity.has(SpeakAction)
        assert not entity.has(WhisperAction)
        assert not entity.has(TransStageAction)
        mock_game.notify_entities.assert_not_called()


# ---------------------------------------------------------------------------
# react() — client-driven 分发：只为传入的实体各发起一次 agent_loop 规划
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_dispatches_one_agent_loop_per_npc_and_applies_submitted(
        self, context: Context, mock_game: MagicMock, system: HomeNpcPlanSystem
    ) -> None:
        """2 个 NPC 传入 → 生成 2 个 agent_loop 任务；每个提交结果都被应用一次。"""
        stage = context.create_entity()
        stage._name = "场景.石台广场"
        stage.add(StageDescriptionComponent, stage.name, "石台广场")
        mock_game.resolve_stage_entity.return_value = stage
        mock_game.get_group.return_value.entities.copy.return_value = set()
        mock_game.get_agent_memory.return_value = MagicMock(messages=[])

        npc1 = _make_actor(context, "角色.NPC_A")
        npc2 = _make_actor(context, "角色.NPC_B")

        def _fake_run(entity: Entity, result: PlanResult) -> bool:
            # 同步占位：react 构建任务列表时会立即调用 _run_agent_loop，
            # 这里直接标记 submitted，便于验证后续串行落库。
            result.submitted = True
            result.action_type = "speak"
            result.target_messages = {"角色.X": "hi"}
            return True

        with (
            patch.object(
                system,
                "_run_agent_loop",
                new=MagicMock(side_effect=_fake_run),
            ) as run_patch,
            patch.object(system, "_apply_submitted_action") as apply_patch,
            patch(
                "src.ai_rpg.systems.home_npc_plan_system.batch_run_boolean_tasks",
                new=AsyncMock(),
            ) as batch_patch,
        ):
            await system.react([npc1, npc2])

        assert run_patch.call_count == 2
        assert batch_patch.await_args is not None
        tasks: List[tuple[str, Any]] = batch_patch.await_args.args[0]
        assert [name for name, _ in tasks] == ["角色.NPC_A", "角色.NPC_B"]
        assert apply_patch.call_count == 2
