from ..models import Stage, StageType
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
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
        stage_profile="你是一个冒险者的临时安全屋，四周是城里一片拥挤的贫民区。安全屋中有帐篷，营火，仓库等设施，虽然简陋，却也足够让人稍事休息，准备下一次冒险。",
        actors=[],
    )

def create_demo_heros_restaurant() -> Stage:

    return create_stage(
        name="场景.餐馆",
        character_sheet_name="restaurant",
        kick_off_message="餐馆里弥漫着美食的香气，许多冒险者和旅人正在这里享用美味的食物，交流各自的经历。",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.HOME,
        stage_profile="你是一个热闹的餐馆，墙上挂满了各地的美食图片，空气中弥漫着诱人的香气。餐馆里有许多桌子，顾客们正在享用美食，交流着各自的冒险故事。",
        actors=[],
    )