"""Demo actors, stages, and world for the multi-agents game framework."""

from .actor_warrior import actor_warrior
from .actor_wizard import actor_wizard
from .actor_goblin import actor_goblin
from .actor_orc import actor_orcs
from .actor_spider import actor_spider
from .stage_heros_camp import stage_heros_camp
from .stage_dungeon1 import stage_dungeon_cave1, create_demo_dungeon1
from .stage_dungeon2 import stage_dungeon_cave2, create_demo_dungeon2
from .stage_dungeon3 import create_demo_dungeon3
from .demo_world import setup_demo_game_world

__all__ = [
    # Demo actors
    "actor_warrior",
    "actor_wizard",
    "actor_goblin",
    "actor_orcs",
    "actor_spider",
    # Demo stages
    "stage_heros_camp",
    "stage_dungeon_cave1",
    "stage_dungeon_cave2",
    "stage_dungeon_cave3",
    # Demo dungeons
    "create_demo_dungeon1",
    "create_demo_dungeon2",
    "create_demo_dungeon3",
    # Demo world
    "setup_demo_game_world",
]
