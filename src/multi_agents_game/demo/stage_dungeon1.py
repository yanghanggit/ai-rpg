from loguru import logger
from multi_agents_game.models import (
    StageType,
    Dungeon,
)

# from multi_agents_game.builder.read_excel_utils import (
#     read_excel_file,
#     list_valid_rows,
#     # safe_extract,
#     safe_get_from_dict,
# )
from multi_agents_game.game.tcg_game_demo_utils import (
    CAMPAIGN_SETTING,
    create_stage,
    # copy_stage,
)
from multi_agents_game.demo.actor_goblin import actor_goblin

########################################################################################################################################
#######################################################################################################################################
# 提取地牢信息

#######################################################################################################################################
#######################################################################################################################################
# 创建地牢场景
stage_dungeon_cave1 = create_stage(
    name="场景.洞窟之一",
    character_sheet_name="goblin_cave",
    kick_off_message="",
    campaign_setting=CAMPAIGN_SETTING,
    type=StageType.DUNGEON,
    stage_profile="你是一个阴暗潮湿的洞窟，四周布满了苔藓和石笋。洞内有哥布林的营地，地上散落着破旧的武器和食物残渣。洞穴深处传来低语声和偶尔的金属碰撞声，似乎有哥布林在进行某种活动。",
    actors=[],
)

####################################################################################################
#######################################################################################################

stage_dungeon_cave1.actors = [actor_goblin]


def create_demo_dungeon1() -> Dungeon:
    return Dungeon(
        name="哥布林洞窟",
        levels=[
            stage_dungeon_cave1,
        ],
    )
