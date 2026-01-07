from .actor_goblin import create_actor_goblin
from ..models import (
    Dungeon,
    StageType,
)
from .global_settings import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_SYSTEM_RULES,
    FANTASY_WORLD_RPG_COMBAT_MECHANICS,
)
from .excel_data_manager import get_excel_data_manager
from .utils import (
    create_stage,
)


def create_demo_dungeon3() -> Dungeon:

    # 添加哥布林角色到地牢场景
    actor_goblin = create_actor_goblin()
    actor_goblin.character_stats.hp = 1

    excel_data_manager = get_excel_data_manager()
    dungeon_data = excel_data_manager.get_dungeon_data("场景.洞窟之三")
    assert dungeon_data is not None, "未找到名为 '场景.洞窟之三' 的地牢数据"

    # 创建地牢场景
    stage_dungeon_cave3 = create_stage(
        name=dungeon_data.name,
        character_sheet_name=dungeon_data.character_sheet_name,
        kick_off_message="",
        type=StageType.DUNGEON,
        stage_profile=dungeon_data.stage_profile,
        actors=[],
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        system_rules=FANTASY_WORLD_RPG_SYSTEM_RULES,
        combat_mechanics=FANTASY_WORLD_RPG_COMBAT_MECHANICS,
    )
    stage_dungeon_cave3.actors = [actor_goblin]

    # 返回地牢对象
    return Dungeon(
        name=dungeon_data.name,
        stages=[
            stage_dungeon_cave3,
        ],
    )
