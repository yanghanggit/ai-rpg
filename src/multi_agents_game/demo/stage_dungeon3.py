from loguru import logger
from ..models import (
    StageType,
    Dungeon,
)
from ..builder.excel_data_manager import dungeon_valid_rows
from .demo_utils import (
    CAMPAIGN_SETTING,
    create_stage,
    # copy_stage,
)
from ..demo.actor_spider import actor_spider

########################################################################################################################################
#######################################################################################################################################
# 使用集中获取的地牢信息 - 现在使用BaseModel而不是Dict[str, Any]
for i, dungeon_data in enumerate(dungeon_valid_rows):
    logger.info(f"\n--- 处理第 {i+1} 行地牢数据 (BaseModel) ---")

    # 直接使用BaseModel的属性，类型安全且有默认值
    name = dungeon_data.name
    character_sheet_name = dungeon_data.character_sheet_name
    stage_profile = dungeon_data.stage_profile
    dungeon_name = dungeon_data.dungeon_name
    actor = dungeon_data.actor

    logger.info(f"地牢名称: {name}")
    logger.info(f"角色表名: {character_sheet_name}")
    logger.info(f"地牢描述: {stage_profile[:50]}...")
    logger.info(f"相关角色: {actor}")

    # 只处理第一行数据
    if i == 0:
        break
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


#######################################################################################################
#########################################################################################################


def create_demo_dungeon3() -> Dungeon:

    stage_dungeon_cave3.actors = [actor_spider]
    actor_spider.rpg_character_profile.hp = 1

    return Dungeon(
        name=dungeon_name,
        levels=[
            stage_dungeon_cave3,
        ],
    )
