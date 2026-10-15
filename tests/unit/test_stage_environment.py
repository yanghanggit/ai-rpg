"""下游对场景环境叙事的「降级继续」行为测试。

环境叙事（EnvironmentComponent.narrative）对下游只是决策补充信息；上游生成失败时，
下游应使用占位文案继续，而非断言崩溃。本文件覆盖：
- get_stage_environment() 的安全读取语义；
- build_planning_context() 在缺组件时仍可构建上下文；
- OpeningInitActorSystem.execute() 在缺组件时仍能完成初始化。
"""

from unittest.mock import MagicMock, patch

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.game.rpg_stage_environment import (
    MISSING_ENVIRONMENT_NARRATIVE,
    get_stage_environment,
)
from ai_rpg.models import ActorComponent, EnvironmentComponent
from ai_rpg.systems.home_planning_prompt_builders import build_planning_context
from ai_rpg.systems.opening_init_actor_system import OpeningInitActorSystem


#######################################################################################################################################
# Helpers
#######################################################################################################################################
def _make_stage(
    context: Context, name: str = "场景.石台广场", env: str | None = None
) -> Entity:
    stage = context.create_entity()
    stage._name = name
    if env is not None:
        stage.add(EnvironmentComponent, name, env)
    return stage


def _make_actor(context: Context, name: str = "角色.玩家A") -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.石台广场")
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


#######################################################################################################################################
# get_stage_environment
#######################################################################################################################################
class TestGetStageEnvironment:
    def test_returns_narrative_when_present(self) -> None:
        stage = _make_stage(Context(), env="石台广场，风里有尘土味")
        assert get_stage_environment(stage) == "石台广场，风里有尘土味"

    def test_returns_placeholder_when_missing(self) -> None:
        stage = _make_stage(Context(), env=None)
        assert get_stage_environment(stage) == MISSING_ENVIRONMENT_NARRATIVE


#######################################################################################################################################
# build_planning_context（家园规划下游）
#######################################################################################################################################
class TestBuildPlanningContext:
    def test_survives_missing_environment(self) -> None:
        context = Context()
        entity = _make_actor(context)
        stage = _make_stage(context, env=None)

        game = MagicMock(spec=DBGGame)
        game.resolve_stage_entity.return_value = stage
        game.get_actors_in_stage.return_value = set()
        game.get_group.return_value.entities.copy.return_value = set()

        planning = build_planning_context(game, entity)

        assert planning.stage_name == "场景.石台广场"
        assert planning.stage_narrative == MISSING_ENVIRONMENT_NARRATIVE


#######################################################################################################################################
# OpeningInitActorSystem.execute（副本开场初始化下游）
#######################################################################################################################################
class TestOpeningInitActorSystemMissingEnvironment:
    @pytest.mark.asyncio
    async def test_execute_survives_missing_environment(self, context: Context) -> None:
        player = _make_actor(context)
        stage = _make_stage(context, name="场景.兽径入口", env=None)

        game = MagicMock(spec=DBGGame)
        game.is_current_room_dungeon_opening = True
        game.current_dungeon_opening_room.initialized = False
        game.get_player_entity.return_value = player
        game.resolve_stage_entity.return_value = stage
        game.get_group.return_value.entities.copy.return_value = set()

        system = OpeningInitActorSystem(game)

        with (
            patch(
                "ai_rpg.systems.opening_init_actor_system.get_alive_actors_in_stage",
                return_value={player},
            ),
            patch.object(
                system, "_inject_opening_scene_environment", autospec=True
            ) as mock_inject,
        ):
            # 缺 EnvironmentComponent 不应抛异常
            await system.execute()

        # 仍完成初始化，且注入的是占位文案
        assert game.current_dungeon_opening_room.initialized is True
        mock_inject.assert_called_once()
        assert (
            mock_inject.call_args.kwargs["environment"] == MISSING_ENVIRONMENT_NARRATIVE
        )
