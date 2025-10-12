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
        kick_off_message="烛火静静地燃烧着。据消息附近的巷子里出现了怪物，需要冒险者前去调查。",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.HOME,
        stage_profile="你是隐藏于自由之城贫民区锈蚀棚户下的一个秘密据点。它外表破败，内部却是一个经过改造的冒险者工坊，配备了基本的魔法屏障、用魔法核心改造的营火，以及便于冒险者们休息和交流的空间。这里是为那些游走于阴影中的冒险者提供的简易却科技增强的的歇脚点，兼具基础生存保障与数据、装备的隐秘存储功能。",
        actors=[],
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )


def create_demo_heros_restaurant() -> Stage:

    return create_stage(
        name="场景.餐馆",
        character_sheet_name="restaurant",
        kick_off_message="餐馆里弥漫着美食的香气，许多冒险者和旅人正在这里享用美味的食物，交流各自的经历。",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.HOME,
        stage_profile="你是一家坐落在自由之城新奥拉西斯街角的酒馆，表面上是一家热闹非凡的冒险者餐厅。粗糙的木桌上摆满了大杯冒着泡沫的蜜酒和香气四溢的烤肉，墙上装饰着巨大的魔物头颅标本、泛黄的遗迹地图和看似用魔法驱动的动态美食壁画（实则为全息投影）。空气中弥漫着烤肉的焦香、浓郁的香料与一种淡淡的、类似臭氧的“魔法”气息。",
        actors=[],
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
