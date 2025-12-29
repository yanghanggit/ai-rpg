"""Test the fixtures in conftest.py to ensure they work correctly."""

from typing import Any


def test_sample_game_fixture(sample_game: Any) -> None:
    """Test that the sample_game fixture creates a valid game instance."""
    assert sample_game is not None
    assert hasattr(sample_game, "name")
    assert sample_game.name == "test_blueprint"
    assert hasattr(sample_game, "player_session")
    assert sample_game.player_session.name == "test_player"
    assert sample_game.player_session.actor == "test_actor"


def test_sample_actor_fixture(sample_actor: Any) -> None:
    """Test that the sample_actor fixture creates a valid actor instance."""
    assert sample_actor is not None
    assert hasattr(sample_actor, "name")
    assert sample_actor.name == "test_actor"
    assert hasattr(sample_actor, "character_sheet")
    assert sample_actor.character_sheet.name == "test_character"
    assert sample_actor.character_sheet.type == "hero"
    assert hasattr(sample_actor, "system_message")
    assert sample_actor.system_message == "test system message"
    assert hasattr(sample_actor, "kick_off_message")
    assert sample_actor.kick_off_message == "test kick off message"
    assert hasattr(sample_actor, "character_stats")
