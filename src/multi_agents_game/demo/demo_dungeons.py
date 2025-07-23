from os import set_inheritable
from loguru import logger
from multi_agents_game.models import (
    StageType,
    Dungeon,
    dungeon,
)
from multi_agents_game.builder.read_excel_utils import (
    read_excel_file,
    list_valid_rows,
    safe_extract,
    safe_get_from_dict,
)
from multi_agents_game.game.tcg_game_demo_utils import (
    CAMPAIGN_SETTING,
    create_stage,
    copy_stage,
)
from multi_agents_game.demo.demo_actors import actor_spider

########################################################################################################################################
#######################################################################################################################################
# 提取地牢信息
file_path = "读表测试.xlsx"
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

stage_heros_camp = create_stage(
    name="场景.营地",
    character_sheet_name="camp",
    kick_off_message="营火静静地燃烧着。据消息附近的洞窟里出现了怪物，需要冒险者前去调查。",
    campaign_setting=CAMPAIGN_SETTING,
    type=StageType.HOME,
    stage_profile="你是一个冒险者的临时营地，四周是一片未开发的原野。营地中有帐篷，营火，仓库等设施，虽然简陋，却也足够让人稍事休息，准备下一次冒险。",
    actors=[],
)

####################################################################################################
#######################################################################################################

stage_dungeon_cave1 = create_stage(
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

stage_dungeon_cave1.actors = [actor_spider]


def create_demo_dungeon1() -> Dungeon:
    return Dungeon(
        name=dungeon_name,
        levels=[
            stage_dungeon_cave1,
        ],
    )
