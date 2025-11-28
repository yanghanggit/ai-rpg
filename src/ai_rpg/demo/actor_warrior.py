from ..models import (
    Actor,
    ActorType,
    CharacterStats,
    Skill,
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
    warrior = create_actor(
        name="角色.战士.卡恩",
        character_sheet_name="warrior",
        kick_off_message="",
        character_stats=CharacterStats(base_max_hp=1000),
        type=ActorType.ALLY,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile=f"""**历史**: 你是曾在砺石角斗场训练的人类精英战士，誓死捍卫新奥拉西斯外环。在“裂隙灾变”中，你率队深入古代遗迹，却遭遇金属瘴气爆发与符文异变，目睹战友被幻觉、被遗迹里的魔法机械吞噬，凭战友的保护和运气捡回一条命。但是想要为死去的战友申请抚恤金时却屡次被拒之门外，从此背离官方体系，成为游离的遗迹冒险者。
**性格**: 你性格坚韧，务实且警惕，深受角斗场生存法则熏陶。
**禁忌**: 你深恶痛绝金属瘴气与失控的古代魔法机械。
**最爱**: 你最爱大块烤肉和烈性黑麦酒。""",
        appearance=f"""接近30岁的人类男性战士，精悍健壮，肌肉线条分明，古铜色肤色。眼神坚毅锐利，下巴有短须，短发略显凌乱。身披厚重符文板甲，镶嵌闪烁的未知金属碎片，胸口佩戴摩挲光滑的金属图腾徽章。背负由遗迹中找到的未知金属打造的长剑，左臂悬挂便携盾牌。右臂有能量爪留下的晶体化疤痕格外醒目，装束沉重实用，混合战场实用与遗迹拾荒风格，覆盖锈迹与尘埃。""",
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )

    warrior.skills = [
        Skill(
            name="快速投掷",
            description="观察场景中的物体，选择一个适合投掷的物体，并将其投掷向指定目标，造成物理伤害。投掷时缺乏防御，受到伤害略微增加。",
        ),
        Skill(
            name="临时掩体",
            description="观察场景中的物体，选择合适的物体快速制造一个临时掩体，提供短暂的保护效果，减少所受伤害。但制造临时掩体消耗体力，使用后下一回合攻击力略微下降。",
        ),
        Skill(
            name="紧急治疗",
            description="观察场景中的物体或者自己身上的东西，选择合适的物品制作处理伤口的工具，进行紧急治疗，恢复一定生命值，但紧急治疗会有概率引发感染，降低防御力",
        ),
        Skill(
            name="最后一击",
            description="消耗大量体力，集中全部力量对敌人发动致命一击，造成高额物理伤害，但使用后会进入力竭状态，防御力大幅下降，下一回合无法行动。",
        ),
        Skill(
            name="利刃斩击",
            description="挥舞带有锋利刃口的武器，对敌人护甲造成毁灭性的切割伤害，使用钝器时伤害减半。但会导致武器过热，下一回合无法使用该武器，且手臂因剧烈震动而暂时麻木，命中率下降。",
        ),
        Skill(
            name="坚不可摧",
            description="摆好防御姿态，举起可用的防具或武器进行格挡，降低所受物理伤害。但格挡持续时间有限，结束后防御力会暂时降低。",
        ),
        Skill(
            name="无畏冲锋",
            description="举起武器撞击敌人并造成物理伤害，随武器特性造成不同效果，钝器有概率使敌人眩晕，利器有概率使敌人流血。但冲锋后会因体力消耗过大，导致下一回合无法行动。",
        ),
        Skill(
            name="防守反击",
            description="使用防具或武器进行格挡，同时寻找机会进行反击，造成物理伤害。但格挡时会消耗体力，攻击力和防御力略微下降。",
        ),
    ]

    return warrior
