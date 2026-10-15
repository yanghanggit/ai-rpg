"""dungeon_spoils_actions 单元测试：奖励与非战斗房间语义。"""

from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    DeckComponent,
    GenerateSpoilsAction,
    PartyMemberComponent,
    SpoilsComponent,
)
from ai_rpg.services.dungeon_spoils_actions import (
    activate_generate_spoils,
    remove_spoils,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_party_member(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "")
    entity.add(DeckComponent, name, [])
    entity.add(PartyMemberComponent, name)
    return entity


def _mock_game(party: set[Entity]) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.is_player_in_dungeon_stage = True
    game.is_current_room_dungeon_combat = False
    group = MagicMock()
    group.entities = party
    game.get_group.return_value = group
    return game


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


# ---------------------------------------------------------------------------
# remove_spoils
# ---------------------------------------------------------------------------


def test_remove_spoils_clears_party(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    member.add(SpoilsComponent, "英雄", [], [])
    game = _mock_game({member})

    ok, _ = remove_spoils(game)

    assert ok is True
    assert not member.has(SpoilsComponent)


def test_remove_spoils_rejects_when_nothing_to_clear(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    game = _mock_game({member})

    ok, _ = remove_spoils(game)

    assert ok is False


def test_remove_spoils_rejects_outside_dungeon(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    member.add(SpoilsComponent, "英雄", [], [])
    game = _mock_game({member})
    game.is_player_in_dungeon_stage = False

    ok, _ = remove_spoils(game)

    assert ok is False
    assert member.has(SpoilsComponent)


# ---------------------------------------------------------------------------
# activate_generate_spoils
# ---------------------------------------------------------------------------


def test_generate_spoils_rejected_in_combat_room(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    game = _mock_game({member})
    game.is_current_room_dungeon_combat = True

    ok, msg = activate_generate_spoils(game)

    assert ok is False
    assert "战斗房间" in msg


def test_generate_spoils_rejected_when_already_generated(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    member.add(SpoilsComponent, "英雄", [], [])
    game = _mock_game({member})

    ok, _ = activate_generate_spoils(game)

    assert ok is False


def test_generate_spoils_activates_action_in_non_combat_room(context: Context) -> None:
    member = _make_party_member(context, "英雄")
    game = _mock_game({member})

    ok, _ = activate_generate_spoils(game)

    assert ok is True
    assert member.has(GenerateSpoilsAction)
