"""CombatRoundCleanupSystem 单元测试。"""

import pytest
from unittest.mock import MagicMock

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    ActorComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models.cards import EffectPhase, StatusEffect
from src.ai_rpg.systems.combat_round_cleanup_system import (
    CombatRoundCleanupSystem,
    _make_status_effects_tick_message,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_effect(name: str, duration: int) -> StatusEffect:
    """创建测试用状态效果。"""
    return StatusEffect(
        name=name,
        description="test",
        phase=EffectPhase.ARBITRATION,
        duration=duration,
    )


def _make_actor_with_effects(
    context: Context, name: str, effects: list[StatusEffect]
) -> Entity:
    """创建挂载 ActorComponent + StatusEffectsComponent 的角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "stage")
    entity.add(StatusEffectsComponent, name, effects)
    return entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    """提供真实 ECS Context，使 Group 自动更新行为正确生效。"""
    return Context()


@pytest.fixture()
def mock_game(context: Context) -> MagicMock:
    """MagicMock TCGGame，将 get_group() 代理到真实 Context。"""
    game = MagicMock(spec=TCGGame)
    game.get_group.side_effect = context.get_group
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> CombatRoundCleanupSystem:
    return CombatRoundCleanupSystem(mock_game)


# ---------------------------------------------------------------------------
# Phase 1 — 纯函数测试
# ---------------------------------------------------------------------------


class TestMakeStatusEffectsTickMessage:
    """_make_status_effects_tick_message 的单元测试。"""

    def test_ticked_effect_shows_remaining_duration(self) -> None:
        """递减后仍存活的效果应显示剩余回合数。"""
        effect = _make_effect("中毒", 2)
        result = _make_status_effects_tick_message([effect], [])
        assert "中毒" in result
        assert "2" in result

    def test_expired_effect_shows_expired_text(self) -> None:
        """已过期的效果应包含"已过期"字样。"""
        effect = _make_effect("燃烧", 0)
        result = _make_status_effects_tick_message([], [effect])
        assert "燃烧" in result
        assert "已过期" in result

    def test_mixed_shows_both(self) -> None:
        """ticked 与 expired 混合时，两者信息均应出现。"""
        ticked = _make_effect("中毒", 1)
        expired = _make_effect("燃烧", 0)
        result = _make_status_effects_tick_message([ticked], [expired])
        assert "中毒" in result
        assert "燃烧" in result
        assert "已过期" in result

    def test_empty_lists_returns_header_only(self) -> None:
        """ticked 与 expired 均为空时，仍返回非空标题行。"""
        result = _make_status_effects_tick_message([], [])
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Phase 2 — tick_status_effects_duration 测试
# ---------------------------------------------------------------------------


class TestTickStatusEffectsDuration:
    """tick_status_effects_duration 的单元测试。"""

    def test_permanent_effect_not_decremented(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """duration == -1 的永久效果不应被递减，也不应触发 add_human_message。"""
        effect = _make_effect("永久祝福", -1)
        _make_actor_with_effects(context, "英雄", [effect])

        system.tick_status_effects_duration()

        mock_game.add_human_message.assert_not_called()
        # 效果仍在，duration 不变
        assert effect.duration == -1

    def test_effect_with_duration_one_expires(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """duration == 1 的效果递减后应从列表中移除，并调用 add_human_message。"""
        effect = _make_effect("中毒", 1)
        actor = _make_actor_with_effects(context, "英雄", [effect])

        system.tick_status_effects_duration()

        comp = actor.get(StatusEffectsComponent)
        assert len(comp.status_effects) == 0
        mock_game.add_human_message.assert_called_once()

    def test_effect_with_duration_two_decrements(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """duration == 2 的效果递减后应保留（duration 变为 1），并调用 add_human_message。"""
        effect = _make_effect("减速", 2)
        actor = _make_actor_with_effects(context, "英雄", [effect])

        system.tick_status_effects_duration()

        comp = actor.get(StatusEffectsComponent)
        assert len(comp.status_effects) == 1
        assert comp.status_effects[0].duration == 1
        mock_game.add_human_message.assert_called_once()

    def test_mixed_effects_handled_correctly(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """永久、将过期、继续存活的效果混合时应各自正确处理。"""
        permanent = _make_effect("祝福", -1)
        expiring = _make_effect("燃烧", 1)
        continuing = _make_effect("中毒", 3)
        actor = _make_actor_with_effects(
            context, "英雄", [permanent, expiring, continuing]
        )

        system.tick_status_effects_duration()

        comp = actor.get(StatusEffectsComponent)
        remaining_names = {e.name for e in comp.status_effects}
        assert "祝福" in remaining_names
        assert "中毒" in remaining_names
        assert "燃烧" not in remaining_names

    def test_no_change_skips_add_human_message(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """所有效果均为永久时，add_human_message 不应被调用。"""
        p1 = _make_effect("祝福", -1)
        p2 = _make_effect("庇护", -1)
        _make_actor_with_effects(context, "英雄", [p1, p2])

        system.tick_status_effects_duration()

        mock_game.add_human_message.assert_not_called()

    def test_multiple_actors_each_processed(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatRoundCleanupSystem,
    ) -> None:
        """多角色时，每个有变化的角色均应调用一次 add_human_message。"""
        _make_actor_with_effects(context, "英雄", [_make_effect("中毒", 1)])
        _make_actor_with_effects(context, "同伴", [_make_effect("燃烧", 1)])

        system.tick_status_effects_duration()

        assert mock_game.add_human_message.call_count == 2


# ---------------------------------------------------------------------------
# Phase 3 — execute() 编排逻辑测试
# ---------------------------------------------------------------------------


class TestExecute:
    """CombatRoundCleanupSystem.execute() 的单元测试。"""

    @pytest.mark.asyncio
    async def test_skip_when_not_ongoing(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """战斗非 ONGOING 时，clear_round_state 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = False
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_no_rounds(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """无任何回合记录时，clear_round_state 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = []
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_round_not_completed(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """最新回合未完成时，clear_round_state 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = [MagicMock()]
        mock_game.current_dungeon.latest_round.is_completed = False
        await system.execute()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_clears_state_when_round_completed(
        self, mock_game: MagicMock, system: CombatRoundCleanupSystem
    ) -> None:
        """最新回合已完成时，clear_round_state 应被调用一次。"""
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = [MagicMock()]
        mock_game.current_dungeon.latest_round.is_completed = True
        await system.execute()
        mock_game.clear_round_state.assert_called_once()
