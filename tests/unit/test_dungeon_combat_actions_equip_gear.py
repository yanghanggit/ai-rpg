from typing import List
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.ai_rpg.models import (
    HandComponent,
    PartyMemberComponent,
)
from src.ai_rpg.models.items import GearItem
from src.ai_rpg.services.dungeon_combat_actions import activate_equip_gear


def _make_game() -> MagicMock:
    game = MagicMock()
    game.is_player_in_dungeon_stage = True
    game.current_dungeon_combat_room.combat.is_ongoing = True
    game.current_dungeon_combat_room.combat.latest_round = SimpleNamespace(
        draw_completed=True,
    )
    return game


def _make_actor(name: str, *, party: bool, hand: bool) -> MagicMock:
    actor = MagicMock()
    actor.name = name
    actor.has.side_effect = lambda component_type: (
        component_type == PartyMemberComponent and party
    ) or (component_type == HandComponent and hand)
    return actor


def _make_player(items: List[GearItem]) -> MagicMock:
    player = MagicMock()
    player.name = "player"
    player.has.return_value = True
    player.get.return_value = SimpleNamespace(items=items)
    return player


def test_activate_equip_gear_rejects_non_party_actor() -> None:
    game = _make_game()
    game.get_entity_by_name.return_value = _make_actor(
        "怪物.测试", party=False, hand=True
    )
    game.get_player_entity.return_value = _make_player([])

    with patch(
        "src.ai_rpg.services.dungeon_combat_actions.get_current_turn_actor",
        return_value="怪物.测试",
    ):
        ok, msg = activate_equip_gear(game, "装备.测试")

    assert ok is False
    assert "不是我方角色" in msg


def test_activate_equip_gear_rejects_missing_hand() -> None:
    game = _make_game()
    game.get_entity_by_name.return_value = _make_actor(
        "角色.测试", party=True, hand=False
    )
    game.get_player_entity.return_value = _make_player([])

    with patch(
        "src.ai_rpg.services.dungeon_combat_actions.get_current_turn_actor",
        return_value="角色.测试",
    ):
        ok, msg = activate_equip_gear(game, "装备.测试")

    assert ok is False
    assert "缺少手牌组件" in msg


def test_activate_equip_gear_activates_action() -> None:
    game = _make_game()
    gear = GearItem(name="装备.测试", description="测试装备")
    actor = _make_actor("角色.测试", party=True, hand=True)
    game.get_entity_by_name.return_value = actor
    game.get_player_entity.return_value = _make_player([gear])

    with patch(
        "src.ai_rpg.services.dungeon_combat_actions.get_current_turn_actor",
        return_value="角色.测试",
    ):
        ok, msg = activate_equip_gear(game, "装备.测试")

    assert ok is True
    assert "成功激活装备使用" in msg
    actor.replace.assert_called_once()
