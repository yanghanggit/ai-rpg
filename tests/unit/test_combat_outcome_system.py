"""CombatOutcomeSystem 单元测试。"""

from typing import List

import pytest
from unittest.mock import MagicMock

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    CombatResult,
    DeathComponent,
    MonsterComponent,
    PartyMemberComponent,
    StageComponent,
)
from src.ai_rpg.systems.combat_outcome_system import (
    CombatOutcomeSystem,
    _get_combat_result_notification,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(
    context: Context,
    name: str,
    *,
    is_ally: bool = False,
    is_monster: bool = False,
    is_dead: bool = False,
) -> Entity:
    """创建带阵营与死亡标记的参战角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "sheet", "stage")
    if is_ally:
        entity.add(PartyMemberComponent, name)
    if is_monster:
        entity.add(MonsterComponent, name)
    if is_dead:
        entity.add(DeathComponent, name)
    return entity


def _make_stage(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(StageComponent, name, "")
    return entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    """提供真实 ECS Context，保证组件操作正确生效。"""
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    """MagicMock DBGGame，预设战斗 ONGOING。"""
    game = MagicMock(spec=DBGGame)
    game.current_combat_room.combat.is_ongoing = True
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> CombatOutcomeSystem:
    return CombatOutcomeSystem(mock_game)


# ---------------------------------------------------------------------------
# Phase 1 — 纯函数测试
# ---------------------------------------------------------------------------


class TestGetCombatResultNotification:
    """_get_combat_result_notification 的单元测试。"""

    def test_victory_contains_victory_text(self) -> None:
        result = _get_combat_result_notification("黑暗地下城", True)
        assert "胜利" in result

    def test_defeat_contains_defeat_text(self) -> None:
        result = _get_combat_result_notification("黑暗地下城", False)
        assert "失败" in result

    def test_stage_name_in_output(self) -> None:
        result = _get_combat_result_notification("血色竞技场", True)
        assert "血色竞技场" in result


# ---------------------------------------------------------------------------
# Phase 2 — 阵营判定方法测试
# ---------------------------------------------------------------------------


class TestIsEnemySideEliminated:
    """_is_enemy_side_eliminated 的单元测试。"""

    def _setup(
        self, mock_game: MagicMock, context: Context, actors: set[Entity]
    ) -> None:
        player = context.create_entity()
        player._name = "player"
        mock_game.get_player_entity.return_value = player
        mock_game.get_actors_in_stage.return_value = actors

    def test_no_enemies_returns_false(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """场景内无怪物时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        self._setup(mock_game, context, {ally})
        assert system._is_enemy_side_eliminated() is False

    def test_alive_enemy_returns_false(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """有存活怪物时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        assert system._is_enemy_side_eliminated() is False

    def test_partial_elimination_returns_false(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """部分怪物死亡时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead_monster = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        alive_monster = _make_actor(context, "巨魔", is_monster=True)
        self._setup(mock_game, context, {ally, dead_monster, alive_monster})
        assert system._is_enemy_side_eliminated() is False

    def test_all_enemies_dead_returns_true(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """全部怪物死亡时应返回 True。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead1 = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        dead2 = _make_actor(context, "骷髅", is_monster=True, is_dead=True)
        self._setup(mock_game, context, {ally, dead1, dead2})
        assert system._is_enemy_side_eliminated() is True


class TestIsPlayerSideEliminated:
    """_is_player_side_eliminated 的单元测试。"""

    def _setup(
        self, mock_game: MagicMock, context: Context, actors: set[Entity]
    ) -> None:
        player = context.create_entity()
        player._name = "player"
        mock_game.get_player_entity.return_value = player
        mock_game.get_actors_in_stage.return_value = actors

    def test_no_allies_returns_false(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """场景内无友方时应返回 False。"""
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {monster})
        assert system._is_player_side_eliminated() is False

    def test_alive_ally_returns_false(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """有存活友方时应返回 False。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        assert system._is_player_side_eliminated() is False

    def test_partial_elimination_returns_false(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """部分友方死亡时应返回 False。"""
        dead_ally = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        alive_ally = _make_actor(context, "同伴", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {dead_ally, alive_ally, monster})
        assert system._is_player_side_eliminated() is False

    def test_all_allies_dead_returns_true(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """全部友方死亡时应返回 True。"""
        dead1 = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        dead2 = _make_actor(context, "同伴", is_ally=True, is_dead=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {dead1, dead2, monster})
        assert system._is_player_side_eliminated() is True


# ---------------------------------------------------------------------------
# Phase 3 — execute() 编排逻辑测试
# ---------------------------------------------------------------------------


class TestExecute:
    """CombatOutcomeSystem.execute() 的单元测试。"""

    def _setup(
        self,
        mock_game: MagicMock,
        context: Context,
        actors: set[Entity],
    ) -> Entity:
        """配置 mock_game 所需返回值，返回 stage_entity。"""
        player = context.create_entity()
        player._name = "player"
        stage = _make_stage(context, "测试场景")
        mock_game.get_player_entity.return_value = player
        mock_game.resolve_stage_entity.return_value = stage
        mock_game.get_actors_in_stage.return_value = actors
        return stage

    @pytest.mark.asyncio
    async def test_skip_when_not_ongoing(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """战斗非 ONGOING 时，complete_combat / clear_round_state 均不应调用。"""
        mock_game.current_combat_room.combat.is_ongoing = False
        await system.execute()
        mock_game.current_combat_room.combat.complete_combat.assert_not_called()
        mock_game.clear_round_state.assert_not_called()
        mock_game.add_human_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_result_when_both_sides_alive(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """双方均有存活时，不应结束战斗。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {ally, monster})
        await system.execute()
        mock_game.current_combat_room.combat.complete_combat.assert_not_called()
        mock_game.clear_round_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_enemy_eliminated_triggers_win(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """敌方全灭时应调用 complete_combat(WIN) 和 clear_round_state。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead_monster = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        self._setup(mock_game, context, {ally, dead_monster})
        await system.execute()
        mock_game.current_combat_room.combat.complete_combat.assert_called_once_with(
            CombatResult.WIN
        )
        mock_game.clear_round_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_enemy_eliminated_broadcasts_to_allies(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """敌方全灭时应向友方广播胜利消息（add_human_message 至少调用一次）。"""
        ally = _make_actor(context, "英雄", is_ally=True)
        dead_monster = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        self._setup(mock_game, context, {ally, dead_monster})
        await system.execute()
        mock_game.add_human_message.assert_called()

    @pytest.mark.asyncio
    async def test_ally_eliminated_triggers_lose(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """友方全灭时应调用 complete_combat(LOSE) 和 clear_round_state。"""
        dead_ally = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {dead_ally, monster})
        await system.execute()
        mock_game.current_combat_room.combat.complete_combat.assert_called_once_with(
            CombatResult.LOSE
        )
        mock_game.clear_round_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_ally_eliminated_broadcasts_to_allies(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """友方全灭时应向（存活/死亡）友方广播失败消息。"""
        dead_ally = _make_actor(context, "英雄", is_ally=True, is_dead=True)
        monster = _make_actor(context, "哥布林", is_monster=True)
        self._setup(mock_game, context, {dead_ally, monster})
        await system.execute()
        mock_game.add_human_message.assert_called()

    @pytest.mark.asyncio
    async def test_clear_round_state_called_before_broadcast(
        self, context: Context, mock_game: MagicMock, system: CombatOutcomeSystem
    ) -> None:
        """clear_round_state 应在 add_human_message 之前调用。"""
        call_order: List[str] = []
        mock_game.clear_round_state.side_effect = lambda: call_order.append("clear")
        mock_game.add_human_message.side_effect = lambda *a, **kw: call_order.append(
            "broadcast"
        )

        ally = _make_actor(context, "英雄", is_ally=True)
        dead_monster = _make_actor(context, "哥布林", is_monster=True, is_dead=True)
        self._setup(mock_game, context, {ally, dead_monster})
        await system.execute()

        assert call_order.index("clear") < call_order.index("broadcast")
