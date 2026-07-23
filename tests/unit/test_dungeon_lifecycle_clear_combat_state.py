"""_clear_combat_state 单元测试：验证战斗结束清理装备组件时，装备物件会被
归还玩家 InventoryComponent，而不是随组件一起被直接丢弃（移动语义）。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.entitas.matcher import Matcher
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    EquippedGearComponent,
    InventoryComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models.items import GearItem
from src.ai_rpg.services.dungeon_lifecycle import _clear_combat_state


def _make_gear(name: str, cost: int = 1) -> GearItem:
    return GearItem(name=name, description="测试装备", cost=cost)


def _make_mock_game(
    context: Context, *, player_entity: Entity, equipped_holders: list[Entity]
) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_player_entity.return_value = player_entity

    def _get_group(matcher: Matcher) -> SimpleNamespace:
        component_types = matcher._all or ()
        if StatusEffectsComponent in component_types:
            return SimpleNamespace(entities=set())
        if EquippedGearComponent in component_types:
            return SimpleNamespace(entities=set(equipped_holders))
        return SimpleNamespace(entities=set())

    game.get_group.side_effect = _get_group
    return game


class TestClearCombatState:
    def test_returns_equipped_gear_to_player_inventory(self) -> None:
        context = Context()

        player = context.create_entity()
        player._name = "player"
        player.add(InventoryComponent, "player", [])

        gear = _make_gear("装备.测试")
        holder = context.create_entity()
        holder._name = "队友A"
        holder.add(EquippedGearComponent, "队友A", gear)

        game = _make_mock_game(context, player_entity=player, equipped_holders=[holder])

        _clear_combat_state(game)

        assert not holder.has(EquippedGearComponent)
        assert gear in player.get(InventoryComponent).items

    def test_no_equipped_gear_leaves_inventory_untouched(self) -> None:
        context = Context()

        player = context.create_entity()
        player._name = "player"
        existing_item = _make_gear("装备.已有")
        player.add(InventoryComponent, "player", [existing_item])

        game = _make_mock_game(context, player_entity=player, equipped_holders=[])

        _clear_combat_state(game)

        assert player.get(InventoryComponent).items == [existing_item]

    def test_raises_when_player_missing_inventory_component(self) -> None:
        context = Context()

        player = context.create_entity()
        player._name = "player"

        game = _make_mock_game(context, player_entity=player, equipped_holders=[])

        with pytest.raises(AssertionError):
            _clear_combat_state(game)
