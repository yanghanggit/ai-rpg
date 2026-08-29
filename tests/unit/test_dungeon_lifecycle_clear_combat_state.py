"""CombatPileTeardownSystem 单元测试：验证 GearItem 转化卡牌离场时装备归还玩家背包。"""

from typing import List
from unittest.mock import MagicMock

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import Card, InventoryComponent
from src.ai_rpg.models.items import GearItem
from src.ai_rpg.systems.combat_pile_teardown_system import CombatPileTeardownSystem


def _make_gear(name: str) -> GearItem:
    return GearItem(name=name, description="测试装备")


def _make_player(context: Context, name: str, items: List[GearItem]) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(InventoryComponent, name, list(items))
    return entity


def _make_mock_game(player: Entity) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_player_entity.return_value = player
    return game


class TestReturnGearFromCard:
    def test_returns_gear_to_player_inventory(self) -> None:
        context = Context()
        player = _make_player(context, "player", [])
        gear = _make_gear("装备.测试")
        card = Card(name="斩击", description="x", gear_item=gear)
        system = CombatPileTeardownSystem(_make_mock_game(player))

        system._return_gear_from_card(card)

        assert card.gear_item is None
        assert gear in player.get(InventoryComponent).items

    def test_noop_when_card_has_no_gear(self) -> None:
        context = Context()
        player = _make_player(context, "player", [])
        card = Card(name="斩击", description="x")
        system = CombatPileTeardownSystem(_make_mock_game(player))

        system._return_gear_from_card(card)

        assert player.get(InventoryComponent).items == []
