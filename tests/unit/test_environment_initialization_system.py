"""EnvironmentInitializationSystem 的「无观察 = 无推理」优化测试。

只对场景内存在存活 Actor 的场景请求环境叙事；没有 Actor 的场景保持惰性，跳过推理。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import StageComponent
from ai_rpg.systems.environment_initialization_system import (
    EnvironmentInitializationSystem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stage(context: Context, name: str) -> Entity:
    stage = context.create_entity()
    stage._name = name
    stage.add(StageComponent, name)
    return stage


def _fake_client(name: str) -> MagicMock:
    client = MagicMock()
    client.name = name
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
def system(mock_game: MagicMock) -> EnvironmentInitializationSystem:
    return EnvironmentInitializationSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestObservedStagesOnly:
    @pytest.mark.asyncio
    async def test_only_stages_with_actors_are_inferred(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EnvironmentInitializationSystem,
    ) -> None:
        """有 Actor 的场景才构建请求；无 Actor 的场景被跳过。"""
        observed = _make_stage(context, "场景.酒馆")
        empty = _make_stage(context, "场景.佣兵公会")
        mock_game.get_group.return_value.entities.copy.return_value = {observed, empty}

        def _has_actors(_game: DBGGame, stage: Entity) -> set[object]:
            return {object()} if stage is observed else set()

        with (
            patch(
                "ai_rpg.systems.environment_initialization_system.get_alive_actors_in_stage",
                side_effect=_has_actors,
            ),
            patch.object(
                system,
                "_build_client",
                side_effect=lambda stage: _fake_client(stage.name),
            ),
            patch.object(system, "_process_environment_response"),
            patch(
                "ai_rpg.systems.environment_initialization_system.batch_chat",
                new=AsyncMock(),
            ) as mock_batch,
        ):
            await system.execute()

        sent_names = [c.name for c in mock_batch.call_args.kwargs["clients"]]
        assert sent_names == ["场景.酒馆"]

    @pytest.mark.asyncio
    async def test_no_observed_stages_skips_inference(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EnvironmentInitializationSystem,
    ) -> None:
        """所有缺环境场景都没有 Actor 时，直接返回，不发起任何请求。"""
        a = _make_stage(context, "场景.酒馆")
        b = _make_stage(context, "场景.佣兵公会")
        mock_game.get_group.return_value.entities.copy.return_value = {a, b}

        with (
            patch(
                "ai_rpg.systems.environment_initialization_system.get_alive_actors_in_stage",
                return_value=set(),
            ),
            patch(
                "ai_rpg.systems.environment_initialization_system.batch_chat",
                new=AsyncMock(),
            ) as mock_batch,
        ):
            await system.execute()

        mock_batch.assert_not_called()
