from ..models import Stage, StageType
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    FANTASY_WORLD_RPG_GAME_COMBAT_MECHANICS,
)
from .utils import (
    create_stage,
)


def create_demo_ally_safe_room() -> Stage:

    return create_stage(
        name="场景.安全屋",
        character_sheet_name="safe_room",
        kick_off_message=""" """,
        type=StageType.HOME,
        stage_profile="""你是位于新奥拉西斯外环「尘烟裂谷」区深处，隐秘冒险者庄园内的一间专属安全屋。
房间四壁由厚重的回收金属板加固，隔绝了外界的喧嚣与瘴气，角落里设有简易的魔法净化装置和舒适的休息铺位。
这里是冒险者在深入遗迹前后的私密整备室，提供绝对的安全感与物资补给功能。""",
        actors=[],
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
        global_combat_mechanics=FANTASY_WORLD_RPG_GAME_COMBAT_MECHANICS,
    )


def create_demo_ally_dining_room() -> Stage:

    return create_stage(
        name="场景.餐厅",
        character_sheet_name="dining_room",
        kick_off_message=""" """,
        type=StageType.HOME,
        stage_profile="""你是位于新奥拉西斯外环「尘烟裂谷」区地下冒险者庄园内的公共食堂，也是热闹非凡的情报中心。
巨大的废弃工业空间内摆满了粗糙长桌，桌上堆积着烤肉与蜜酒，墙上挂着魔物标本和实时更新的遗迹悬赏令。
空气中弥漫着食物的焦香与酒精味，冒险者们在此大声喧哗，交换着关于遗迹深处异变与宝藏的最新情报。""",
        actors=[],
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
        global_combat_mechanics=FANTASY_WORLD_RPG_GAME_COMBAT_MECHANICS,
    )


def create_stage_monitoring_house() -> Stage:

    return create_stage(
        name="场景.监视之屋",
        character_sheet_name="monitoring_house",
        kick_off_message="",
        type=StageType.HOME,
        stage_profile="你是一个监视之屋，房间里漆黑一片，唯独有一块屏幕能看见新奥拉西斯城内外的各个地方。只有玩家能进入这里，并通过屏幕穿梭于各个场景。",
        actors=[],
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
        global_combat_mechanics=FANTASY_WORLD_RPG_GAME_COMBAT_MECHANICS,
    )
