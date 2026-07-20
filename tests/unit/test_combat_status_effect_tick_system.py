"""CombatStatusEffectTickSystem 单元测试。"""

from typing import List
from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    PhaseType,
    StatusEffect,
    StatusEffectsComponent,
)
from src.ai_rpg.systems.combat_status_effect_tick_system import (
    CombatStatusEffectTickSystem,
    _make_status_effects_tick_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _effect(name: str, duration: int) -> StatusEffect:
    return StatusEffect(
        name=name, description="test", phase=PhaseType.ARBITRATION, duration=duration
    )


def _make_actor(ctx: Context, name: str, effects: List[StatusEffect]) -> Entity:
    entity = ctx.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "stage")
    entity.add(StatusEffectsComponent, name, effects)
    return entity


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
def system(game: MagicMock) -> CombatStatusEffectTickSystem:
    return CombatStatusEffectTickSystem(game)


# ---------------------------------------------------------------------------
# _make_status_effects_tick_message
# ---------------------------------------------------------------------------


def test_tick_message_ticked_shows_remaining() -> None:
    result = _make_status_effects_tick_message([_effect("中毒", 2)], [])
    assert "中毒" in result and "2" in result


def test_tick_message_expired_shows_text() -> None:
    result = _make_status_effects_tick_message([], [_effect("燃烧", 0)])
    assert "燃烧" in result and "已过期" in result


# ---------------------------------------------------------------------------
# tick_status_effects_duration
# ---------------------------------------------------------------------------


def test_tick_permanent_unchanged_no_message(
    ctx: Context, game: MagicMock, system: CombatStatusEffectTickSystem
) -> None:
    """duration == -1 永久效果不递减，不写上下文。"""
    actor = _make_actor(ctx, "英雄", [_effect("祝福", -1)])
    system.tick_status_effects_duration()
    assert actor.get(StatusEffectsComponent).status_effects[0].duration == -1
    game.add_human_message.assert_not_called()


def test_tick_effect_expires_at_one(
    ctx: Context, game: MagicMock, system: CombatStatusEffectTickSystem
) -> None:
    """duration == 1 效果到期后移除，写入一次上下文。"""
    actor = _make_actor(ctx, "英雄", [_effect("中毒", 1)])
    system.tick_status_effects_duration()
    assert actor.get(StatusEffectsComponent).status_effects == []
    game.add_human_message.assert_called_once()


def test_tick_effect_decrements_and_retains(
    ctx: Context, game: MagicMock, system: CombatStatusEffectTickSystem
) -> None:
    """duration > 1 时递减保留，写入上下文。"""
    actor = _make_actor(ctx, "英雄", [_effect("减速", 3)])
    system.tick_status_effects_duration()
    assert actor.get(StatusEffectsComponent).status_effects[0].duration == 2
    game.add_human_message.assert_called_once()


def test_tick_mixed_effects(
    ctx: Context, game: MagicMock, system: CombatStatusEffectTickSystem
) -> None:
    """永久/到期/存活效果混合：各自独立处理，结果只保留永久与存活。"""
    actor = _make_actor(
        ctx, "英雄", [_effect("祝福", -1), _effect("燃烧", 1), _effect("中毒", 3)]
    )
    system.tick_status_effects_duration()
    names = {e.name for e in actor.get(StatusEffectsComponent).status_effects}
    assert names == {"祝福", "中毒"}


# ---------------------------------------------------------------------------
# execute() 编排逻辑
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skips_when_not_ongoing(
    game: MagicMock, system: CombatStatusEffectTickSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = False
    await system.execute()
    game.get_group.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_when_no_rounds(
    game: MagicMock, system: CombatStatusEffectTickSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = []
    await system.execute()
    game.get_group.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_when_round_not_completed(
    game: MagicMock, system: CombatStatusEffectTickSystem
) -> None:
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = [MagicMock()]
    game.current_combat_room.combat.latest_round.is_completed = False
    await system.execute()
    game.get_group.assert_not_called()


@pytest.mark.asyncio
async def test_execute_ticks_when_completed(
    ctx: Context, game: MagicMock, system: CombatStatusEffectTickSystem
) -> None:
    """回合完成时应推进状态效果时钟。"""
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.rounds = [MagicMock()]
    game.current_combat_room.combat.latest_round.is_completed = True
    _make_actor(ctx, "英雄", [_effect("中毒", 1)])

    await system.execute()

    game.add_human_message.assert_called_once()
