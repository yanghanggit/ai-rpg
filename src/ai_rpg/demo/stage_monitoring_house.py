from ..models import (
    StageType,
)
from ..models.objects import Stage
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_stage,
)


def create_stage_monitoring_house() -> Stage:

    return create_stage(
        name="场景.监视之屋",
        character_sheet_name="monitoring_house",
        kick_off_message="",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.HOME,
        stage_profile="你是一个监视之屋，房间里漆黑一片，唯独有一块屏幕能看见新奥拉西斯城内外的各个地方。只有玩家XYZ能进入这里，并通过屏幕穿梭于各个场景。",
        actors=[],
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
