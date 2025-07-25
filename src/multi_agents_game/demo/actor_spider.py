from loguru import logger
from ..models import (
    ActorType,
    RPGCharacterProfile,
)
from ..builder.excel_data_manager import actor_valid_rows
from ..game.tcg_game_demo_utils import (
    CAMPAIGN_SETTING,
    create_actor,
)

#######################################################################################################################################
#######################################################################################################################################
# 使用集中获取的角色信息 - 现在使用BaseModel而不是Dict[str, Any]
for i, actor_data in enumerate(actor_valid_rows):
    logger.info(f"\n--- 处理第 {i+1} 行角色数据 (BaseModel) ---")

    # 直接使用BaseModel的属性，类型安全且有默认值
    name = actor_data.name
    character_sheet_name = actor_data.character_sheet_name
    actor_profile = actor_data.actor_profile
    appearance = actor_data.appearance

    logger.info(f"角色名称: {name}")
    logger.info(f"角色表名: {character_sheet_name}")
    logger.info(f"角色描述: {actor_profile[:50]}...")
    logger.info(f"角色外观: {appearance[:50]}...")

    # 只处理第一行数据
    if i == 0:
        break

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
