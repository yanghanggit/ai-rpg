"""TurnEndArbitrationSystem 单元测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    Card,
    HandComponent,
    PassTurnAction,
    TargetType,
)
from src.ai_rpg.systems.turn_end_arbitration_system import TurnEndArbitrationSystem


def _make_card(name: str, *, turn_end: bool = False) -> Card:
    return Card(
        name=name,
        description="测试卡牌",
        on_turn_end_affixes=["[灼烧]:回合结束时对持有者造成伤害"] if turn_end else [],
        playable=not turn_end,
        retain=turn_end,
        damage=1,
        hit_count=1,
        target_type=TargetType.SINGLE,
        self_target=True,
    )


def _make_actor(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "dungeon")
    entity.add(HandComponent, name, [])
    return entity


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.current_dungeon_combat_room.combat.is_ongoing = True
    game.current_dungeon_combat_room.combat.rounds = [object()]
    stage = MagicMock()
    stage.has.return_value = True
    stage.get.return_value = SimpleNamespace(narrative="测试场景环境")
    game.resolve_stage_entity.return_value = stage
    game.get_agent_memory.return_value = SimpleNamespace(messages=[])
    return game


class TestCollectHandTurnEndCards:
    def test_returns_only_turn_end_cards(
        self, context: Context, mock_game: MagicMock
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        actor = _make_actor(context, "英雄")
        actor.get(HandComponent).cards.extend(
            [
                _make_card("普通牌"),
                _make_card("灼纹", turn_end=True),
                _make_card("另一张普通牌"),
            ]
        )

        cards = system._collect_hand_turn_end_cards(actor)

        assert [c.name for c in cards] == ["灼纹"]


class TestTurnEndArbitrationSystem:
    def test_filter_requires_pass_turn_action(
        self, context: Context, mock_game: MagicMock
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        entity = context.create_entity()
        assert system.filter(entity) is False

        entity.add(PassTurnAction, "英雄")
        assert system.filter(entity) is True

    @pytest.mark.asyncio
    async def test_react_skips_when_not_ongoing(
        self, context: Context, mock_game: MagicMock
    ) -> None:
        mock_game.current_dungeon_combat_room.combat.is_ongoing = False
        system = TurnEndArbitrationSystem(mock_game)
        entity = context.create_entity()
        entity.add(PassTurnAction, "英雄")

        with patch(
            "src.ai_rpg.systems.turn_end_arbitration_system.agent_loop"
        ) as mock_agent_loop:
            await system.react([entity])

        mock_agent_loop.assert_not_called()

    @pytest.mark.asyncio
    async def test_react_skips_when_no_turn_end_cards(
        self, context: Context, mock_game: MagicMock
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        pass_entity = _make_actor(context, "英雄")
        pass_entity.add(PassTurnAction, "英雄")
        pass_entity.get(HandComponent).cards.append(_make_card("普通牌"))

        with patch(
            "src.ai_rpg.systems.turn_end_arbitration_system.agent_loop"
        ) as mock_agent_loop:
            await system.react([pass_entity])

        mock_agent_loop.assert_not_called()

    @pytest.mark.asyncio
    async def test_react_with_holder_calls_agent_loop(
        self, context: Context, mock_game: MagicMock
    ) -> None:
        system = TurnEndArbitrationSystem(mock_game)
        holder = _make_actor(context, "怪物.纸人")
        holder.add(PassTurnAction, "怪物.纸人")
        holder.get(HandComponent).cards.append(_make_card("灼纹", turn_end=True))

        with (
            patch(
                "src.ai_rpg.systems.turn_end_arbitration_system.get_alive_actors_in_stage",
                return_value={holder},
            ),
            patch(
                "src.ai_rpg.systems.turn_end_arbitration_system.agent_loop",
                new=AsyncMock(return_value=True),
            ) as mock_agent_loop,
        ):
            await system.react([holder])

        assert mock_agent_loop.await_count == 1
        assert mock_agent_loop.await_args is not None
        assert mock_agent_loop.await_args.kwargs["name"] == "怪物.纸人"
