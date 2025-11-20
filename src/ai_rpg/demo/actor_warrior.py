from ..models import (
    Actor,
    ActorType,
    CharacterStats,
)
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_actor,
)


def create_actor_warrior() -> Actor:
    """
    创建一个战士角色实例，这是测试的人物！

    Returns:
        Actor: 战士角色实例
    """
    return create_actor(
        name="角色.战士.卡恩",
        character_sheet_name="warrior",
        kick_off_message="",
        character_stats=CharacterStats(base_max_hp=1000),
        type=ActorType.ALLY,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile=f"""**历史**: 你曾是人类王国阿斯特拉的边境守护者。家乡饱受"地脉扰劫"——古代遗迹能量泄露引发的异变与构装体失控——的摧残，在"黯影裂口"之战中，你亲眼目睹了狂暴的火焰魔法如何将生命与大地化为灰烬。
**性格**: 你性格坚韧，务实且警惕，深受边境军民特有的实用主义影响。
**禁忌**: 你深恶痛绝不受控制的火焰能量、滥用火焰魔法和失控能量。
**最爱**: 你最爱大块烤肉和烈性黑麦酒。""",
        appearance=f"""接近30岁的人类男性战士，精悍健壮，肌肉线条分明，古铜色肤色。眼神坚毅锐利，下巴有短须，短发略显凌乱。身披染有旧渍的复合纤维战术背心，胸口佩戴摩挲光滑的金属图腾徽章。背负高频振动长剑，携带古老精密的能源弩，左臂悬挂能量力场便携盾牌。右臂有能量爪留下的晶体化疤痕格外醒目，装束沉重实用，带战火与辐射尘埃痕迹。""",
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
