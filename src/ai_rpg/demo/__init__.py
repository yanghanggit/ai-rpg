"""Demo actors, stages, and world for the multi-agents game framework."""

from .actor_goblin import create_actor_goblin
from .actor_orc import create_actor_orc
from .actor_training_robot import create_actor_training_robot
from .actor_warrior import create_actor_warrior
from .actor_wizard import create_actor_wizard
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .excel_data import ActorExcelData, DungeonExcelData
from .excel_data_manager import ExcelDataManager, get_excel_data_manager
from .stage_dungeon1 import create_demo_dungeon1
from .stage_dungeon2 import create_demo_dungeon2
from .stage_dungeon3 import create_demo_dungeon3
from .stage_dungeon4 import create_demo_dungeon4
from .stage_dungeon5 import create_demo_dungeon5
from .stage_dungeon6 import create_demo_dungeon6
from .stage_heros_camp import create_demo_heros_camp
from .world import create_demo_game_world_boot1, create_demo_game_world_boot2

__all__ = [
    "create_actor_warrior",
    "create_actor_wizard",
    "create_actor_goblin",
    "create_actor_orc",
    "create_actor_training_robot",
    "create_demo_heros_camp",
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
    "create_demo_game_world_boot1",
    "create_demo_game_world_boot2",
]
