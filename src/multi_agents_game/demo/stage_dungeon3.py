from loguru import logger
from ..models import (
    StageType,
    Dungeon,
)
from ..builder.read_excel_utils import (
    read_excel_file,
    list_valid_rows,
    # safe_extract,
    safe_get_from_dict,
)
from ..game.tcg_game_demo_utils import (
    CAMPAIGN_SETTING,
    create_stage,
    # copy_stage,
)
from ..demo.actor_spider import actor_spider

########################################################################################################################################
#######################################################################################################################################
# 提取地牢信息
file_path = "excel_test.xlsx"
sheet_name = "dungeons"

df = read_excel_file(file_path, sheet_name)
if df is None:
    logger.error("无法读取Excel文件")
    valid_rows = []
else:
    valid_rows = list_valid_rows(df)
    if not valid_rows:
        logger.warning("没有找到有效数据行")

for i, row_data in enumerate(valid_rows):
    logger.info(f"\n--- 处理第 {i+1} 行有效数据 ---")

    name = safe_get_from_dict(row_data, "name", "未命名地牢")
    character_sheet_name = safe_get_from_dict(
        row_data, "character_sheet_name", "default_dungeon"
    )
    stage_profile = safe_get_from_dict(
        row_data,
        "stage_profile",
        "默认地牢描述：一个神秘的地牢，等待冒险者探索。",
    )
    dungeon_name = safe_get_from_dict(row_data, "dungeon_name")
    actor = safe_get_from_dict(row_data, "actor", "默认怪物")
#######################################################################################################################################
#######################################################################################################################################
# 创建地牢场景
stage_dungeon_cave3 = create_stage(
    name=name,
    character_sheet_name=character_sheet_name,
    kick_off_message="",
    campaign_setting=CAMPAIGN_SETTING,
    type=StageType.DUNGEON,
    stage_profile=stage_profile,
    actors=[],
)

####################################################################################################
#######################################################################################################

stage_dungeon_cave3.actors = [actor_spider]
actor_spider.rpg_character_profile.hp = 1

#######################################################################################################
#########################################################################################################

def create_demo_dungeon3() -> Dungeon:
    return Dungeon(
        name=dungeon_name,
        levels=[
            stage_dungeon_cave3,
        ],
    )
