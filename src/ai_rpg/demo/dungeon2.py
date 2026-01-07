from .actor_orc import create_actor_orc
from ..models import Dungeon, Stage, StageType
from .global_settings import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_SYSTEM_RULES,
    FANTASY_WORLD_RPG_COMBAT_MECHANICS,
)
from .utils import (
    create_stage,
)


def create_stage_cave2() -> Stage:
    """
    创建一个兽人洞窟场景实例

    Returns:
        Stage: 兽人洞窟场景实例
    """
    return create_stage(
        name="场景.洞窟之二",
        character_sheet_name="goblin_cave",
        kick_off_message="",
        type=StageType.DUNGEON,
        stage_profile="你是一个阴暗潮湿的洞窟，四周布满了苔藓和石笋，地上散落着破旧的武器和食物残渣。",
        actors=[],
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        system_rules=FANTASY_WORLD_RPG_SYSTEM_RULES,
        combat_mechanics=FANTASY_WORLD_RPG_COMBAT_MECHANICS,
    )


def create_demo_dungeon2() -> Dungeon:

    actor_orc = create_actor_orc()
    actor_orc.character_stats.hp = 1

    stage_cave2 = create_stage_cave2()
    stage_cave2.actors = [actor_orc]

    return Dungeon(
        name="兽人洞窟",
        stages=[
            stage_cave2,
        ],
    )
