from ..models import (
    Actor,
    ActorCharacterSheet,
    ActorType,
    CharacterStats,
    Skill,
)
from .global_settings import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_SYSTEM_RULES,
)
from .utils import (
    create_actor,
)


def create_actor_goblin() -> Actor:
    """
    创建一个哥布林角色实例

    Returns:
        Actor: 哥布林角色实例
    """
    goblin = create_actor(
        name="角色.怪物.哥布林-拉格",
        character_sheet=ActorCharacterSheet(
            name="goblin",
            type=ActorType.ENEMY.value,
            profile="你是哥布林部落中狡黠而略聪明的成员,生活在新奥拉西斯附近的丛林里。一次外出觅食时误入古代遗迹，你捡到发光的金属碎片和嗡鸣的机械造物，当作神赐武器与工具，用来改善部落生活。尽管部落长老警告这些是危险的不祥遗物，你仍坚持使用，梦想改变哥布林卑微的命运。",
            base_body="",
            appearance="""身材比普通哥布林略微高挑，瘦削却敏捷。皮肤呈暗绿色，眼睛闪着黄褐色的光，透出无时无刻的警惕。鼻子小而上翘，双耳显得尖长。身上穿戴着从古代科技遗迹里找到的废弃金属做成的简易护甲，破旧的背包里装着许多自己制造的哥布林飞刀，腰间还挂着一把锈迹斑斑的短剑。整体装束显得杂乱无章，但透露出一股机敏与狡黠的气息。""",
        ),
        # kick_off_message="",
        character_stats=CharacterStats(),
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        system_rules=FANTASY_WORLD_RPG_SYSTEM_RULES,
    )
    goblin.skills = [
        Skill(
            name="飞刀投掷",
            description="从背包中掏出一把哥布林飞刀，快速投掷向敌人，造成物理伤害。但投掷后需要重新装填，降低下一回合的攻击力。",
        ),
        Skill(
            name="快速治疗",
            description="使用破布治疗自己，但会降低下一回合的攻击力。",
        ),
    ]

    return goblin
