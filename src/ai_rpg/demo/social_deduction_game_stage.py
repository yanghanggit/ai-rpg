from ..models import Stage, StageType
from .utils import (
    create_stage,
)
from .campaign_setting import WEREWOLF_CAMPAIGN_SETTING, WEREWOLF_GLOBAL_GAME_MECHANICS


def create_demo_werewolf_stage() -> Stage:

    return create_stage(
        name="场景.中央广场",
        character_sheet_name="werewolf_stage",
        kick_off_message="月影村的夜晚降临了，村民们聚集在村中央的广场上。烛火摇曳，每个人的脸庞都笼罩在阴影中。狼人已经潜伏在你们中间，生死游戏即将开始...",
        campaign_setting=WEREWOLF_CAMPAIGN_SETTING,
        type=StageType.HOME,
        stage_profile="你是月影村的中央广场，这里是村民们聚集讨论和进行投票的主要场所。广场中央有一个古老的石台，四周摆放着木制长椅。夜晚时分，火把和烛火为这里提供微弱的照明，营造出神秘而紧张的氛围。白天时这里是村民们辩论和寻找狼人的地方，夜晚则成为各种神秘力量活动的舞台。你见证着每一次投票的结果，记录着每个人的命运。",
        actors=[],
        global_game_mechanics=WEREWOLF_GLOBAL_GAME_MECHANICS,
    )
