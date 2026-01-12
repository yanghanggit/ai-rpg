from .actor_goblin import create_actor_goblin
from ..models import (
    Dungeon,
    StageProfile,
    StageType,
)
from ..models.entities import Stage
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
    RPG_COMBAT_MECHANICS,
)
from .utils import (
    create_stage,
)


def create_stage_cave1() -> Stage:

    return create_stage(
        name="场景.洞窟之一",
        stage_profile=StageProfile(
            name="goblin_cave",
            type=StageType.DUNGEON,
            profile="你是一个黑暗干燥的洞窟，地上都是易燃的干草，墙上插着各种箭矢，地上还有破损的盔甲和断剑。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )
