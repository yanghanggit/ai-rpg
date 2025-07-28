# from loguru import logger
from ..models import (
    # StageType,
    Dungeon,
)

# from multi_agents_game.builder.read_excel_utils import (
#     read_excel_file,
#     list_valid_rows,
#     # safe_extract,
#     safe_get_from_dict,
# )
from ..game.tcg_game_demo_utils import (
    CAMPAIGN_SETTING,
    # create_stage,
    copy_stage,
)
from ..demo.stage_dungeon1 import stage_dungeon_cave1
from ..demo.actor_orc import actor_orcs

########################################################################################################################################
#######################################################################################################################################
# 提取地牢信息

#######################################################################################################################################
#######################################################################################################################################
# 创建地牢场景
stage_dungeon_cave2 = copy_stage(
    name="场景.洞窟之二",
    stage_character_sheet=stage_dungeon_cave1.character_sheet,
    kick_off_message="",
    campaign_setting=CAMPAIGN_SETTING,
    actors=[],
)

####################################################################################################
#######################################################################################################

####################################################################################################
#######################################################################################################


def create_demo_dungeon2() -> Dungeon:

    stage_dungeon_cave2.actors = [actor_orcs]
    actor_orcs.rpg_character_profile.hp = 1

    return Dungeon(
        name="兽人洞窟",
        levels=[
            stage_dungeon_cave2,
        ],
    )
