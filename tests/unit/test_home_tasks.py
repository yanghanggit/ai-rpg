"""家园任务层测试：验证动作在任务内、pipeline 之前激活。"""

from types import SimpleNamespace
from typing import Any, List, Tuple, cast
from unittest.mock import AsyncMock, patch

import pytest

from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.game.game_server import GameServer
from ai_rpg.services import home_tasks
from ai_rpg.services.game_server_runtime import bind_runtime_game_server


class _FakeHomeGame:
    is_player_in_home_stage = True


async def _make_server_with_game() -> GameServer:
    server = GameServer()
    room = await server.create_room("u1")
    room._dbg_game = cast(DBGGame, _FakeHomeGame())
    bind_runtime_game_server(server)
    return server


async def test_run_home_task_activates_before_pipeline() -> None:
    await _make_server_with_game()
    calls: List[str] = []

    def activate(game: DBGGame) -> Tuple[bool, str]:
        calls.append("activate")
        return True, ""

    async def run_pipeline(game: DBGGame) -> None:
        calls.append("pipeline")

    context: Any = SimpleNamespace(job=SimpleNamespace(id=1))
    with patch.object(home_tasks, "store_game_async", AsyncMock()):
        await home_tasks._run_home_task(context, "u1", activate, run_pipeline)

    assert calls == ["activate", "pipeline"]


async def test_run_home_task_skips_pipeline_when_activate_fails() -> None:
    await _make_server_with_game()
    calls: List[str] = []

    def activate(game: DBGGame) -> Tuple[bool, str]:
        calls.append("activate")
        return False, "boom"

    async def run_pipeline(game: DBGGame) -> None:
        calls.append("pipeline")

    context: Any = SimpleNamespace(job=SimpleNamespace(id=1))
    with (
        patch.object(home_tasks, "store_game_async", AsyncMock()),
        patch.object(home_tasks, "save_task_error") as save_error,
    ):
        with pytest.raises(ValueError):
            await home_tasks._run_home_task(context, "u1", activate, run_pipeline)

    assert calls == ["activate"]
    save_error.assert_called_once()
