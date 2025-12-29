"""Demo actors, stages, and world for the multi-agents game framework."""

from .actor_goblin import create_actor_goblin
from .actor_orc import create_actor_orc
from .actor_training_robot import create_actor_training_robot
from .actor_warrior import create_actor_warrior
from .actor_wizard import create_actor_wizard
from .actor_player import create_actor_player
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .excel_data import ActorExcelData, DungeonExcelData
from .excel_data_manager import ExcelDataManager, get_excel_data_manager
from .dungeon1 import create_demo_dungeon1
from .dungeon2 import create_demo_dungeon2
from .dungeon3 import create_demo_dungeon3
from .dungeon4 import create_demo_dungeon4
from .dungeon5 import create_demo_dungeon5
from .dungeon6 import create_demo_dungeon6
from .stage_ally_manor import (
    create_demo_ally_safe_room,
    create_demo_ally_dining_room,
    create_stage_monitoring_house,
)
from .world import (
    create_demo_game_world_blueprint1,
    create_demo_game_world_blueprint2,
    create_demo_game_world_blueprint3,
)

__all__ = [
    "create_actor_player",
    "create_actor_warrior",
    "create_actor_wizard",
    "create_actor_goblin",
    "create_actor_orc",
    "create_actor_training_robot",
    "create_demo_ally_safe_room",
    "create_demo_ally_dining_room",
    "create_stage_monitoring_house",
    "create_demo_dungeon1",
    "create_demo_dungeon2",
    "create_demo_dungeon3",
    "create_demo_dungeon4",
    "create_demo_dungeon5",
    "create_demo_dungeon6",
    "FANTASY_WORLD_RPG_CAMPAIGN_SETTING",
    "DungeonExcelData",
    "ActorExcelData",
    "ExcelDataManager",
    "get_excel_data_manager",
    "create_demo_game_world_blueprint1",
    "create_demo_game_world_blueprint2",
    "create_demo_game_world_blueprint3",
]
