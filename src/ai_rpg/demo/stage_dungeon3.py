from ..demo.actor_spider import create_actor_spider
from ..models import (
    Dungeon,
    StageType,
)
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .excel_data_manager import get_excel_data_manager
from .utils import (
    create_stage,
)


def create_demo_dungeon3() -> Dungeon:

    # 添加蜘蛛角色到地牢场景
    actor_spider = create_actor_spider()
    actor_spider.rpg_character_profile.hp = 1

    excel_data_manager = get_excel_data_manager()
    dungeon_data = excel_data_manager.get_dungeon_data("场景.洞窟之三")
    assert dungeon_data is not None, "未找到名为 '场景.洞窟之三' 的地牢数据"

    # 创建地牢场景
    stage_dungeon_cave3 = create_stage(
        name=dungeon_data.name,
        character_sheet_name=dungeon_data.character_sheet_name,
        kick_off_message="",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.DUNGEON,
        stage_profile=dungeon_data.stage_profile,
        actors=[],
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
    stage_dungeon_cave3.actors = [actor_spider]

    # 返回地牢对象
    return Dungeon(
        name=dungeon_data.name,
        stages=[
            stage_dungeon_cave3,
        ],
    )
