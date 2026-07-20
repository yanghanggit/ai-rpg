from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.ai_rpg.models import (
    EquippedGearComponent,
    InventoryComponent,
    PartyMemberComponent,
)
from src.ai_rpg.models.items import GearItem
from src.ai_rpg.services.dungeon_actions import activate_use_gear


def _make_game(*, current_actor: str, player_name: str = "player") -> MagicMock:
    game = MagicMock()
    game.is_player_in_dungeon_stage = True
    game.current_combat_room.combat.is_ongoing = True
    game.current_combat_room.combat.latest_round = SimpleNamespace(
        draw_completed=True,
        current_actor=current_actor,
    )

    player = MagicMock()
    player.name = player_name
    player.has.side_effect = lambda component_type: component_type in {
        PartyMemberComponent,
        InventoryComponent,
    }
    game.get_player_entity.return_value = player
    game.get_group.return_value.entities = set()
    return game


def test_activate_use_gear_requires_inventory_holder_turn() -> None:
    game = _make_game(current_actor="ally", player_name="player")

    ok, msg = activate_use_gear(game, "装备.测试", ["player"])

    assert ok is False
    assert "不是背包持有者" in msg


def test_activate_use_gear_rejects_when_target_energy_less_than_cost() -> None:
    game = _make_game(current_actor="player", player_name="player")
    gear = GearItem(name="装备.测试", description="测试装备", cost=2)
    player = game.get_player_entity.return_value
    player.get.return_value = SimpleNamespace(items=[gear])
    target = MagicMock()
    target.name = "队友A"
    game.get_entity_by_name.return_value = target

    with (
        patch(
            "src.ai_rpg.services.dungeon_actions.resolve_targets",
            return_value=(["队友A"], ""),
        ),
        patch("src.ai_rpg.services.dungeon_actions.get_energy", return_value=1),
    ):
        ok, msg = activate_use_gear(game, "装备.测试", ["队友A"])

    assert ok is False
    assert "需要2点" in msg
    player.replace.assert_not_called()


def test_activate_use_gear_rejects_when_item_already_equipped() -> None:
    game = _make_game(current_actor="player", player_name="player")
    gear = GearItem(name="装备.测试", description="测试装备", cost=1)
    player = game.get_player_entity.return_value
    player.get.return_value = SimpleNamespace(items=[gear])
    holder = MagicMock()
    holder.name = "队友A"
    holder.get.return_value = EquippedGearComponent(name="队友A", item=gear)
    game.get_group.return_value.entities = {holder}

    ok, msg = activate_use_gear(game, "装备.测试", ["队友A"])

    assert ok is False
    assert "当前已被 队友A 装备中" in msg
    player.replace.assert_not_called()


def test_activate_use_gear_activates_action_when_target_energy_covers_cost() -> None:
    game = _make_game(current_actor="player", player_name="player")
    gear = GearItem(name="装备.测试", description="测试装备", cost=2)
    player = game.get_player_entity.return_value
    player.get.return_value = SimpleNamespace(items=[gear])
    target = MagicMock()
    target.name = "队友A"
    game.get_entity_by_name.return_value = target

    with (
        patch(
            "src.ai_rpg.services.dungeon_actions.resolve_targets",
            return_value=(["队友A"], ""),
        ),
        patch("src.ai_rpg.services.dungeon_actions.get_energy", return_value=2),
    ):
        ok, msg = activate_use_gear(game, "装备.测试", ["队友A"])

    assert ok is True
    assert "成功激活装备使用" in msg
    player.replace.assert_called_once()
