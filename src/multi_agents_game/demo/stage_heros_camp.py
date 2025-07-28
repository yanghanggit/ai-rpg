from ..models import (
    StageType,
)

from .demo_utils import (
    CAMPAIGN_SETTING,
    create_stage,
)

stage_heros_camp = create_stage(
    name="场景.营地",
    character_sheet_name="camp",
    kick_off_message="营火静静地燃烧着。据消息附近的洞窟里出现了怪物，需要冒险者前去调查。",
    campaign_setting=CAMPAIGN_SETTING,
    type=StageType.HOME,
    stage_profile="你是一个冒险者的临时营地，四周是一片未开发的原野。营地中有帐篷，营火，仓库等设施，虽然简陋，却也足够让人稍事休息，准备下一次冒险。",
    actors=[],
)
