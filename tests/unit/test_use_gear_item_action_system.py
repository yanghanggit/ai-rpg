"""UseGearItemActionSystem 单元测试：验证以 energy 消耗替代耐久约束的装备机制。"""

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    EquippedGearComponent,
    InventoryComponent,
    PartyMemberComponent,
    RoundStatsComponent,
    UseGearItemAction,
)
from src.ai_rpg.models.items import GearItem
from src.ai_rpg.models.target_type import TargetType
from src.ai_rpg.systems.use_gear_item_action_system import UseGearItemActionSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gear(name: str) -> GearItem:
    return GearItem(
        name=name,
        description="测试装备",
        target_type=TargetType.ALLY_SINGLE,
    )


def _make_player_entity(
    context: Context,
    name: str,
    items: List[GearItem],
    action_item: GearItem,
    targets: List[str],
) -> Entity:
    """创建持有 InventoryComponent + UseGearItemAction 的 player 实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(InventoryComponent, name, list(items))
    entity.add(UseGearItemAction, name, action_item, targets)
    return entity


def _make_party_entity(context: Context, name: str, energy: int) -> Entity:
    """创建带 RoundStatsComponent（当前回合剩余 energy）的友方角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(PartyMemberComponent, name)
    entity.add(RoundStatsComponent, name, energy)
    return entity


def _setup_mock_dungeon(mock_game: MagicMock, *, round_count: int = 1) -> None:
    mock_game.current_dungeon.is_ongoing = True
    mock_game.current_dungeon.current_rounds = [MagicMock()] * round_count
    mock_game.current_dungeon.latest_round = MagicMock()
    # 无任何角色已装备该物品
    mock_game.get_group.return_value.entities = set()


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
def system(mock_game: MagicMock) -> UseGearItemActionSystem:
    return UseGearItemActionSystem(mock_game)


# ---------------------------------------------------------------------------
# react()
# ---------------------------------------------------------------------------


class TestReact:
    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        mock_game.current_dungeon.is_ongoing = False
        gear = _make_gear("装备.测试")
        player = _make_player_entity(context, "player", [gear], gear, ["队友A"])

        await system.react([player])

        mock_game.get_entity_by_name.assert_not_called()

    @pytest.mark.asyncio
    async def test_target_energy_deducted_by_one(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        gear = _make_gear("装备.测试")
        player = _make_player_entity(context, "player", [gear], gear, ["队友A"])
        target = _make_party_entity(context, "队友A", energy=3)
        mock_game.get_entity_by_name.return_value = target

        with patch(
            "src.ai_rpg.systems.use_gear_item_action_system.get_alive_actors_in_stage",
            return_value=set(),
        ):
            await system.react([player])

        assert target.get(RoundStatsComponent).energy == 2
        assert target.get(EquippedGearComponent).item.name == "装备.测试"

    @pytest.mark.asyncio
    async def test_advance_turn_called_after_equip(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        _setup_mock_dungeon(mock_game)
        gear = _make_gear("装备.测试")
        player = _make_player_entity(context, "player", [gear], gear, ["队友A"])
        target = _make_party_entity(context, "队友A", energy=1)
        mock_game.get_entity_by_name.return_value = target

        with (
            patch(
                "src.ai_rpg.systems.use_gear_item_action_system.get_alive_actors_in_stage",
                return_value=set(),
            ),
            patch(
                "src.ai_rpg.systems.use_gear_item_action_system.advance_turn"
            ) as mock_advance_turn,
        ):
            await system.react([player])

        mock_advance_turn.assert_called_once_with(
            mock_game, mock_game.current_dungeon.latest_round
        )
        assert target.get(RoundStatsComponent).energy == 0

    @pytest.mark.asyncio
    async def test_raises_when_target_energy_already_zero(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UseGearItemActionSystem,
    ) -> None:
        """系统信任调用方（activate_use_gear）已校验目标 energy>0；
        若目标 energy 已耗尽仍被调用，consume_energy 内部断言应失败。"""
        _setup_mock_dungeon(mock_game)
        gear = _make_gear("装备.测试")
        player = _make_player_entity(context, "player", [gear], gear, ["队友A"])
        target = _make_party_entity(context, "队友A", energy=0)
        mock_game.get_entity_by_name.return_value = target

        with patch(
            "src.ai_rpg.systems.use_gear_item_action_system.get_alive_actors_in_stage",
            return_value=set(),
        ):
            with pytest.raises(AssertionError):
                await system.react([player])
