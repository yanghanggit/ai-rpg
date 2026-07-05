"""CombatRoundCleanupSystem 单元测试。"""

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from src.ai_rpg.deepseek import DeepSeekClient
from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    CharacterStatsComponent,
    PhaseType,
    StatusEffect,
    StatusEffectsComponent,
)
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.systems.combat_round_cleanup_system import (
    CombatRoundCleanupSystem,
    _make_round_end_hp_update_message,
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
def system(game: MagicMock) -> CombatRoundCleanupSystem:
    return CombatRoundCleanupSystem(game)


# ---------------------------------------------------------------------------
# _make_round_end_hp_update_message
# ---------------------------------------------------------------------------


def test_round_end_hp_message_contains_values() -> None:
    result = _make_round_end_hp_update_message(17, 30)
    assert "17" in result and "30" in result


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
    ctx: Context, game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    """duration == -1 永久效果不递减，不写上下文。"""
    actor = _make_actor(ctx, "英雄", [_effect("祝福", -1)])
    system.tick_status_effects_duration()
    assert actor.get(StatusEffectsComponent).status_effects[0].duration == -1
    game.add_human_message.assert_not_called()


def test_tick_effect_expires_at_one(
    ctx: Context, game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    """duration == 1 效果到期后移除，写入一次上下文。"""
    actor = _make_actor(ctx, "英雄", [_effect("中毒", 1)])
    system.tick_status_effects_duration()
    assert actor.get(StatusEffectsComponent).status_effects == []
    game.add_human_message.assert_called_once()


def test_tick_effect_decrements_and_retains(
    ctx: Context, game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    """duration > 1 时递减保留，写入上下文。"""
    actor = _make_actor(ctx, "英雄", [_effect("减速", 3)])
    system.tick_status_effects_duration()
    assert actor.get(StatusEffectsComponent).status_effects[0].duration == 2
    game.add_human_message.assert_called_once()


def test_tick_mixed_effects(
    ctx: Context, game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    """永久/到期/存活效果混合：各自独立处理，结果只保留永久与存活。"""
    actor = _make_actor(
        ctx, "英雄", [_effect("祝福", -1), _effect("燃烧", 1), _effect("中毒", 3)]
    )
    system.tick_status_effects_duration()
    names = {e.name for e in actor.get(StatusEffectsComponent).status_effects}
    assert names == {"祝福", "中毒"}


# ---------------------------------------------------------------------------
# _apply_round_end_effect_response
# ---------------------------------------------------------------------------


def _make_client(name: str, json_str: str) -> MagicMock:
    client = MagicMock(spec=DeepSeekClient)
    client.name = name
    client.prompt = "prompt"
    client.response_content = json_str
    client.response_ai_message = AIMessage(content=json_str)
    return client


@patch("src.ai_rpg.systems.combat_round_cleanup_system.set_character_hp")
def test_apply_valid_response_updates_hp(mock_set_hp: MagicMock, ctx: Context) -> None:
    """LLM 返回合法 JSON 时 set_character_hp 应被调用。"""
    game = _make_game(ctx)
    entity = _make_actor(ctx, "英雄", [])
    entity.add(CharacterStatsComponent, "英雄", CharacterStats(hp=20, max_hp=30))
    game.get_entity_by_name.return_value = entity
    mock_set_hp.return_value = MagicMock(hp=17, max_hp=30)
    system = CombatRoundCleanupSystem(game)

    system._apply_round_end_effect_response(
        _make_client("英雄", '{"hp": 17, "combat_log": "中毒发作"}')
    )

    mock_set_hp.assert_called_once_with(entity, 17)


@patch("src.ai_rpg.systems.combat_round_cleanup_system.set_character_hp")
def test_apply_invalid_response_no_raise(mock_set_hp: MagicMock, ctx: Context) -> None:
    """LLM 返回无法解析的内容时不抛出，set_character_hp 不被调用。"""
    game = _make_game(ctx)
    entity = _make_actor(ctx, "英雄", [])
    entity.add(CharacterStatsComponent, "英雄", CharacterStats(hp=20, max_hp=30))
    game.get_entity_by_name.return_value = entity
    system = CombatRoundCleanupSystem(game)

    system._apply_round_end_effect_response(_make_client("英雄", "not valid json"))

    mock_set_hp.assert_not_called()


# ---------------------------------------------------------------------------
# execute() 编排逻辑
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_skips_when_not_ongoing(
    game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    game.current_dungeon.is_ongoing = False
    await system.execute()
    game.clear_round_state.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_when_no_rounds(
    game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    game.current_dungeon.is_ongoing = True
    game.current_dungeon.current_rounds = []
    await system.execute()
    game.clear_round_state.assert_not_called()


@pytest.mark.asyncio
async def test_execute_skips_when_round_not_completed(
    game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    game.current_dungeon.is_ongoing = True
    game.current_dungeon.current_rounds = [MagicMock()]
    game.current_dungeon.latest_round.is_completed = False
    await system.execute()
    game.clear_round_state.assert_not_called()


@pytest.mark.asyncio
async def test_execute_clears_state_when_completed(
    game: MagicMock, system: CombatRoundCleanupSystem
) -> None:
    game.current_dungeon.is_ongoing = True
    game.current_dungeon.current_rounds = [MagicMock()]
    game.current_dungeon.latest_round.is_completed = True
    await system.execute()
    game.clear_round_state.assert_called_once()
