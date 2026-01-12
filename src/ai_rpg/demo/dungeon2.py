from .actor_orc import create_actor_orc
from ..models import Dungeon, Stage, StageProfile, StageType
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
    RPG_COMBAT_MECHANICS,
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
        stage_profile=StageProfile(
            name="goblin_cave",
            type=StageType.DUNGEON,
            profile="你是一个阴暗潮湿的洞窟，四周布满了苔藓和石笋，地上散落着破旧的武器和食物残渣。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )
