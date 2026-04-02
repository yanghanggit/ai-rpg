"""
沙漠遗迹地下城副本工厂模块

本模块用于创建沙漠残垣世界观下的遗迹相关地下城副本。

核心内容：
- create_sand_wolf_ruins_dungeon: 单场景副本，挑战遗迹外缘的沙狼（常物），适合初期狩猎练习。
"""

from ..models import (
    Dungeon,
    DungeonRoom,
    StageProfile,
    StageType,
)

from .actor_sand_wolf import create_actor_sand_wolf
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
)
from .entity_factory import (
    create_stage,
)
from .rpg_system_rules import (
    RPG_SYSTEM_RULES,
)


def create_sand_wolf_ruins_dungeon() -> Dungeon:
    """
    创建沙狼遗迹副本。

    包含单个场景：
    - 残柱外沿：遗迹外缘的开阔沙地，常物级沙狼的活动领域

    Returns:
        Dungeon: 沙狼遗迹副本实例
    """
    stage_ruins_outskirts = create_stage(
        name="场景.残柱外沿",
        stage_profile=StageProfile(
            name="ruins_outskirts",
            type=StageType.DUNGEON,
            profile="""你是沙漠残垣遗迹外缘的开阔地带，几根已倒塌或半倒的断柱散落在沙地上，截面朝向各异。
地面是松软的沙土与裸露的岩板交替分布，风在断柱之间卷起低矮的沙尘旋涡。柱身背风侧积着细沙，风向一侧则磨蚀痕迹明显。
日落前后，气温迅速下降，沙面在余光中反射出橙红色调。断柱投下长而倾斜的阴影，阴影边缘处沙土颜色明显更暗。""",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    actor_wolf = create_actor_sand_wolf()
    stage_ruins_outskirts.actors = [actor_wolf]

    return Dungeon(
        name="地下城.沙漠残垣",
        ecology="遗迹外缘散落的断柱与沙地交界处。松软沙土上留有大量宽爪印迹，深浅不一，部分印迹已被风沙半掩。断柱根部背风侧有浅凹，沙面压实，是沙狼白天蜷伏的痕迹。偶尔可见被咬断的小型骨骼碎片半埋在沙中。",
        rooms=[
            DungeonRoom(stage=stage_ruins_outskirts),
        ],
    )
