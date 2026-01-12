"""Demo actors, stages, and world for the multi-agents game framework."""

from .actor_goblin import create_actor_goblin
from .actor_orc import create_actor_orc
from .actor_training_dummy import create_training_dummy
from .actor_hunter import create_hunter
from .actor_wizard import create_actor_wizard
from .actor_player import create_actor_player
from .global_settings import RPG_CAMPAIGN_SETTING
from .dungeon1 import create_demo_dungeon1
from .dungeon2 import create_demo_dungeon2

# from .dungeon3 import create_demo_dungeon3
from .dungeon4 import create_demo_dungeon4
from .dungeon_training import create_training_dungeon

# from .dungeon6 import create_demo_dungeon6
from .stage_village import (
    create_hunter_storage,
    create_village_hall,
    create_shi_family_house,
)
from .world import (
    create_demo_game_world_blueprint1,
    create_demo_single_hunter_blueprint,
    create_demo_game_world_blueprint3,
)

__all__ = [
    "create_actor_player",
    "create_hunter",
    "create_actor_wizard",
    "create_actor_goblin",
    "create_actor_orc",
    "create_training_dummy",
    "create_hunter_storage",
    "create_village_hall",
    "create_shi_family_house",
    "create_demo_dungeon1",
    "create_demo_dungeon2",
    # "create_demo_dungeon3",
    "create_demo_dungeon4",
    "create_training_dungeon",
    # "create_demo_dungeon6",
    "RPG_CAMPAIGN_SETTING",
    "create_demo_game_world_blueprint1",
    "create_demo_single_hunter_blueprint",
    "create_demo_game_world_blueprint3",
]
