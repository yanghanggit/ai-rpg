"""Test configuration and fixtures."""

import pytest
from typing import Type, Optional, Any

try:
    from src.ai_rpg.game.tcg_game import TCGGame
    from src.ai_rpg.models.objects import Actor
    from src.ai_rpg.models.character_sheet import ActorCharacterSheet
    from src.ai_rpg.models.objects import RPGCharacterProfile, Inventory
    from src.ai_rpg.models.world import World, Boot
    from src.ai_rpg.models.dungeon import Dungeon
    from src.ai_rpg.game.player_client import PlayerClient

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
        agents_chat_history={},
        dungeon=dungeon,
        boot=boot,
    )
    player = PlayerClient(name="test_player", actor="test_actor")
    return _TCGGame(
        name="test_game",
        player_client=player,
        world=world,
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
        inventory=Inventory(items=[]),
    )
