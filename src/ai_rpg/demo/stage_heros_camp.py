from ..models import Stage, StageType
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_stage,
)


def create_demo_heros_camp() -> Stage:

    return create_stage(
        name="场景.安全屋",
        character_sheet_name="safe_house",
        kick_off_message="""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。""",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.HOME,
        stage_profile="""你是隐藏于新奥拉西斯外环「尘烟裂谷」区锈蚀棚户下的秘密据点。
外表破败，内部却是经过改造的冒险者工坊，配备了基本的魔法屏障、用魔法核心改造的营火，以及便于冒险者们休息和交流的空间。
这里为游走于阴影中的冒险者提供简易的歇脚点，兼具基础生存保障与装备的隐秘存储功能。""",
        actors=[],
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )


def create_demo_heros_restaurant() -> Stage:

    return create_stage(
        name="场景.餐馆",
        character_sheet_name="restaurant",
        kick_off_message="""# 游戏启动! 以第三人称视角，直接描写场景内部的可见环境。
        
使用纯粹的感官描写：视觉、听觉、嗅觉、触觉等具体细节。
输出为单段紧凑文本，不使用换行或空行。

## 环境叙事基调
餐馆里弥漫着美食的香气，模糊的人影在木桌间交错，嘈杂的交谈声混成低沉的背景音。
这些人影是环境氛围的一部分，作为整体存在感呈现，不应被描述为具体的个体或互动行为。""",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.HOME,
        stage_profile="""你是坐落在新奥拉西斯中环市场区街角的一家酒馆，热闹非凡的冒险者餐厅。
粗糙的木桌上摆满了大杯冒着泡沫的蜜酒和香气四溢的烤肉，墙上装饰着巨大的魔物头颅标本、泛黄的遗迹地图和看似用魔法驱动的动态美食壁画（实则为全息投影）。
空气中弥漫着烤肉的焦香、浓郁的香料与一种淡淡的、类似臭氧的魔法气息。""",
        actors=[],
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
