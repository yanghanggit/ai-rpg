"""CombatRoundCleanupSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.systems.combat_round_cleanup_system import CombatRoundCleanupSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(ctx: Context) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = ctx.get_group
    return game


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx() -> Context:
    return Context()


@pytest.fixture()
def game(ctx: Context) -> MagicMock:
    return _make_game(ctx)


@pytest.fixture()
def system(game: MagicMock) -> CombatRoundCleanupSystem:
    return CombatRoundCleanupSystem(game)


# ---------------------------------------------------------------------------
# execute() 编排逻辑
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skips_when_not_ongoing(
    game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = False
    await system.execute()
    game.clear_round_state.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_when_no_rounds(
    game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = []
    await system.execute()
    game.clear_round_state.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_when_round_not_completed(
    game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = [MagicMock()]
    game.current_combat_room.combat.latest_round.is_completed = False
    await system.execute()
    game.clear_round_state.assert_not_called()


@pytest.mark.asyncio
async def test_execute_clears_state_when_completed(
    game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = [MagicMock()]
    game.current_combat_room.combat.latest_round.is_completed = True
    await system.execute()
    game.clear_round_state.assert_called_once()
