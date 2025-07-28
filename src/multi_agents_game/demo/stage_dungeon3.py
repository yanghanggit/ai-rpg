from ..models import (
    StageType,
    Dungeon,
)
from ..excel_builder.excel_data_manager import excel_data_manager
from .demo_utils import (
    CAMPAIGN_SETTING,
    create_stage,
)
from ..demo.actor_spider import actor_spider
import copy


def create_demo_dungeon3() -> Dungeon:

    dungeon_data = excel_data_manager.get_dungeon_data("场景.洞窟之三")
    assert dungeon_data is not None, "未找到名为 '场景.洞窟之三' 的地牢数据"

    # 创建地牢场景
    stage_dungeon_cave3 = create_stage(
        name=dungeon_data.name,
        character_sheet_name=dungeon_data.character_sheet_name,
        kick_off_message="",
        campaign_setting=CAMPAIGN_SETTING,
        type=StageType.DUNGEON,
        stage_profile=dungeon_data.stage_profile,
        actors=[],
    )

    # 添加蜘蛛角色到地牢场景
    copy_actor_spider = copy.deepcopy(actor_spider)
    stage_dungeon_cave3.actors = [copy_actor_spider]
    copy_actor_spider.rpg_character_profile.hp = 1

    # 返回地牢对象
    return Dungeon(
        name=dungeon_data.name,
        levels=[
            stage_dungeon_cave3,
        ],
    )
