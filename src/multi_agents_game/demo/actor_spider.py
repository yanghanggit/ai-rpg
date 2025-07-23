from loguru import logger
from ..models import (
    ActorType,
    RPGCharacterProfile,
)
from multi_agents_game.builder.read_excel_utils import (
    read_excel_file,
    list_valid_rows,
    safe_get_from_dict,
)
from ..game.tcg_game_demo_utils import (
    CAMPAIGN_SETTING,
    create_actor,
)

#######################################################################################################################################
#######################################################################################################################################
file_path = "excel_test.xlsx"
sheet_name = "actors"

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

    # 提取地牢信息
    name = safe_get_from_dict(row_data, "name", "未命名怪物")
    character_sheet_name = safe_get_from_dict(
        row_data, "character_sheet_name", "default_monster"
    )
    actor_profile = safe_get_from_dict(
        row_data,
        "actor_profile",
        "默认怪物描述：一个神秘的怪物，等待冒险者探索。",
    )
    appearance = safe_get_from_dict(row_data, "appearance", "默认怪物外观：")

########################################################################################################################################
actor_spider = create_actor(
    name=name,
    character_sheet_name=character_sheet_name,
    kick_off_message="",
    rpg_character_profile=RPGCharacterProfile(base_dexterity=1),
    type=ActorType.MONSTER,
    campaign_setting=CAMPAIGN_SETTING,
    actor_profile=actor_profile,
    appearance=appearance,
)
