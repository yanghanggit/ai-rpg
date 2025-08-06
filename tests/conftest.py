"""Test configuration and fixtures."""

import pytest
from pathlib import Path
from typing import Type, Optional, Any

try:
    from src.multi_agents_game.game.tcg_game import TCGGame
    from src.multi_agents_game.models.objects import Actor
    from src.multi_agents_game.models.character_sheet import ActorCharacterSheet
    from src.multi_agents_game.models.objects import RPGCharacterProfile
    from src.multi_agents_game.models.world import World, Boot
    from src.multi_agents_game.models.dungeon import Dungeon
    from src.multi_agents_game.game.player_proxy import PlayerProxy
    from src.multi_agents_game.chat_services.chat_system import ChatSystem
    from src.multi_agents_game.chaos_engineering.empty_engineering_system import (
        EmptyChaosEngineeringSystem,
    )

    _TCGGame: Optional[Type[TCGGame]] = TCGGame
    _Actor: Optional[Type[Actor]] = Actor
except ImportError:
    # 在包未完全安装时跳过导入
    _TCGGame = None
    _Actor = None


@pytest.fixture
def sample_game() -> Any:
    """Create a sample game for testing."""
    if _TCGGame is None:
        pytest.skip("TCGGame not available")

    # 创建基本的依赖
    boot = Boot(name="test_boot")
    dungeon = Dungeon(name="")
    world = World(
        runtime_index=1000,
        entities_snapshot=[],
        agents_short_term_memory={},
        dungeon=dungeon,
        boot=boot,
    )
    player = PlayerProxy(name="test_player", actor="test_actor")
    chat_system = ChatSystem(
        name="test_chat", username="test_user", localhost_urls=["http://localhost:8000"]
    )
    chaos_system = EmptyChaosEngineeringSystem()

    return _TCGGame(
        name="test_game",
        player=player,
        world=world,
        chat_system=chat_system,
        chaos_engineering_system=chaos_system,
    )


@pytest.fixture
def sample_actor() -> Any:
    """Create a sample actor for testing."""
    if _Actor is None:
        pytest.skip("Actor not available")

    character_sheet = ActorCharacterSheet(
        name="test_character",
        type="hero",
        profile="test profile",
        appearance="test appearance",
    )

    rpg_profile = RPGCharacterProfile()

    return _Actor(
        name="test_actor",
        character_sheet=character_sheet,
        system_message="test system message",
        kick_off_message="test kick off message",
        rpg_character_profile=rpg_profile,
    )
