from ..models import (
    Actor,
    CharacterSheet,
    ActorType,
    CharacterStats,
    Skill,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
)
from .entity_factory import (
    create_actor,
)
from .common_skills import (
    WEAPON_ATTACK_SKILL,
    WEAPON_DEFEND_SKILL,
    PERCEPTION_SKILL,
)


def create_mystic() -> Actor:
    """
    创建术士角色实例（云音）。

    该角色是桃花源中研究古先民符文的年轻女术士，自幼学习草药与符文之学，
    能够感知并解读古先民遗迹中的灵气波动与神秘符文。她温和沉静，
    对未知事物充满好奇，是村落中少数能够沟通古今知识的学者。

    Returns:
        Actor: 术士角色实例，包含完整的角色属性、技能和背景设定
    """
    actor = create_actor(
        name="角色.术士.云音",
        character_sheet=CharacterSheet(
            name="mystic_yun",
            type=ActorType.ALLY,
            profile=f"""**历史**：你是桃花源中少数能够解读古先民符文的年轻女子。自幼随祖母学习草药与符文之学，某次随猎人探查古先民遗迹时，意外触碰到一块发光的石刻，自此便能感知到遗迹中残留的微弱灵气波动。你开始潜心研究那些神秘的石刻符文，试图理解古先民是如何引导自然之力的。村中长者既敬重你的学识，又担忧你过度深入古先民的禁忌领域。
**性格**：你性格温和沉静，但对未知事物充满好奇。面对古先民遗迹的谜题时，你会变得专注而执着。
**说话风格**：日常温柔平和，探讨学问时认真严谨。
**禁忌**：你厌恶对古先民遗迹的盲目破坏，反对将知识封锁独占。
**最爱**：你喜欢收集各类古老器物与竹简，最爱桃花茶配糯米糕。
  """,
            base_body="",
            appearance=f"""年轻女子，身形纤细，肤色白皙。眼神清澈沉静，乌黑长发挽成简单的发髻，发间插着一支古朴的玉簪。身着素色交领长袍，袖口和衣襟绣有简单的云纹。腰间系着麻布包袱，内装竹简、草药包与几块刻有符文的古旧石片。手持一根竹杖，杖头缠绕着采自山中的藤蔓，藤蔓间夹着几片发出微光的特殊叶片。左手腕戴着用古先民遗迹中发现的青铜碎片打磨成的手镯。整体装束简朴雅致，带有淡淡的草药与墨香。""",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # 定义术士的技能
    actor.skills = [
        WEAPON_ATTACK_SKILL.model_copy(),
        WEAPON_DEFEND_SKILL.model_copy(),
        PERCEPTION_SKILL.model_copy(),
    ]

    return actor
