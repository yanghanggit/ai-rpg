"""Test configuration and fixtures."""

import pytest

from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorType,
    Blueprint,
    CharacterStats,
    Dungeon,
    PlayerSession,
    WorldState,
)
from ai_rpg.models.entities import Actor


@pytest.fixture
def sample_game() -> DBGGame:
    """Create a sample game for testing."""
    # 创建基本的依赖
    blueprint = Blueprint(
        name="test_blueprint",
        player_actor="test_player_actor",
        campaign_setting="test_setting",
        system_rules="",
        knowledge_base={},
        stages=[],
        world_entities=[],
    )
    dungeon = Dungeon(name="", rooms=[], profile="")
    world = WorldState(
        entity_counter=1000,
        entities=[],
        agent_memories={},
        dungeon=dungeon,
        blueprint=blueprint,
    )
    player = PlayerSession(
        name="test_player", actor="test_actor", game="test_blueprint"
    )
    return DBGGame(
        name="test_blueprint",
        player_session=player,
        world=world,
    )


@pytest.fixture
def sample_actor() -> Actor:
    """Create a sample actor for testing."""
    return Actor(
        name="test_actor",
        type=ActorType.NPC,
        profile="test profile",
        base_body="",
        system_message="test system message",
        character_stats=CharacterStats(max_hp=50, attack=10, defense=5),
    )
