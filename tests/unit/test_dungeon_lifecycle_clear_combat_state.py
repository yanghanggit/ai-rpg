"""CombatPileTeardownSystem 单元测试：验证 EquippedGearComponent 装备归还玩家背包。"""

from typing import List
from unittest.mock import MagicMock

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import EquippedGearComponent, InventoryComponent
from src.ai_rpg.models.items import GearItem
from src.ai_rpg.systems.combat_pile_teardown_system import CombatPileTeardownSystem


def _make_gear(name: str) -> GearItem:
    return GearItem(name=name, description="测试装备")


def _make_player(context: Context, name: str, items: List[GearItem]) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(InventoryComponent, name, list(items))
    return entity


def _make_gear_holder(context: Context, name: str, gears: List[GearItem]) -> Entity:
    """创建携带 EquippedGearComponent 的角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(EquippedGearComponent, name, list(gears))
    return entity


def _make_mock_game(context: Context, player: Entity) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_group.side_effect = context.get_group
    game.get_player_entity.return_value = player
    return game


class TestReturnEquippedGear:
    def test_returns_gear_to_player_inventory(self) -> None:
        context = Context()
        player = _make_player(context, "player", [])
        gear = _make_gear("装备.测试")
        holder = _make_gear_holder(context, "角色.测试", [gear])
        system = CombatPileTeardownSystem(_make_mock_game(context, player))

        system._return_equipped_gear()

        assert gear in player.get(InventoryComponent).items
        assert not holder.has(EquippedGearComponent)

    def test_multiple_holders_gear_all_returned(self) -> None:
        context = Context()
        player = _make_player(context, "player", [])
        gear_a = _make_gear("装备.A")
        gear_b = _make_gear("装备.B")
        holder_a = _make_gear_holder(context, "角色.A", [gear_a])
        holder_b = _make_gear_holder(context, "角色.B", [gear_b])
        system = CombatPileTeardownSystem(_make_mock_game(context, player))

        system._return_equipped_gear()

        inventory = player.get(InventoryComponent).items
        assert gear_a in inventory
        assert gear_b in inventory
        assert not holder_a.has(EquippedGearComponent)
        assert not holder_b.has(EquippedGearComponent)

    def test_noop_when_no_equipped_gear(self) -> None:
        context = Context()
        player = _make_player(context, "player", [])
        system = CombatPileTeardownSystem(_make_mock_game(context, player))

        system._return_equipped_gear()

        assert player.get(InventoryComponent).items == []
