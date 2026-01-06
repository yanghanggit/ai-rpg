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
    actor = create_actor(
        name="角色.战士.卡恩",
        character_sheet_name="warrior",
        kick_off_message="",
        character_stats=CharacterStats(),
        type=ActorType.ALLY,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile=f"""**历史**: 你是曾在砺石角斗场训练的人类精英战士，誓死捍卫新奥拉西斯的安全。在“裂隙灾变”中，你率队深入时空裂隙，却遭遇金属瘴气爆发与符文异变，目睹战友被幻觉、被裂隙遗迹里的魔法机械吞噬，凭战友的保护和运气捡回一条命。但是想要为死去的战友申请抚恤金时却屡次被拒之门外，从此背离官方体系，成为游离的遗迹冒险者。
**性格**: 你性格坚韧，务实且警惕，深受角斗场生存法则熏陶。
**禁忌**: 你深恶痛绝金属瘴气与失控的古代魔法机械。
**最爱**: 你最爱大块烤肉和烈性黑麦酒。""",
        appearance=f"""接近30岁的人类男性战士，精悍健壮，肌肉线条分明，古铜色肤色。眼神坚毅锐利，下巴有短须，短发略显凌乱。身披厚重符文板甲，镶嵌闪烁的未知金属碎片，胸口佩戴摩挲光滑的金属图腾徽章。背负由遗迹中找到的未知金属打造的长剑，左臂悬挂便携短刃。右臂有能量爪留下的晶体化疤痕格外醒目，装束沉重实用，混合战场实用与遗迹拾荒风格，覆盖锈迹与尘埃。""",
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )

    actor.skills = [
        Skill(
            name="快速投掷",
            description="观察场景中的物体，选择一个适合投掷的物体，并将其投掷向指定目标，造成物理伤害。投掷时缺乏防御，受到伤害略微增加。",
        ),
        Skill(
            name="物体利用",
            description="通过自身力量利用环境中的物体或使用自身装备，将其转化为攻击的手段。但过度驱使会导致物体损坏，且施法者需要分散注意力维持控制。",
        ),
        Skill(
            name="怒气姿态",
            description="摆出威慑性的战斗姿态，激发体内狂暴力量，大幅提升攻击力和气势。但盛怒状态会削弱理智判断，导致防御力下降。",
        ),
        Skill(
            name="最后一击",
            description="消耗大量体力，集中全部力量对敌人发动致命一击，造成高额物理伤害，但使用后会进入力竭状态，防御力大幅下降，下一回合无法行动。",
        ),
        Skill(
            name="利刃斩击",
            description="挥舞近战武器，对敌人护甲造成毁灭性的切割伤害，使用钝器时伤害减半。但会导致武器过热，下一回合无法使用该武器，且手臂因剧烈震动而暂时麻木。",
        ),
        Skill(
            name="无畏冲锋",
            description="举起武器撞击敌人并造成物理伤害，随武器特性造成不同效果，钝器有概率使敌人眩晕，利器有概率使敌人流血。但冲锋后会因体力消耗过大，导致下一回合无法行动。",
        ),
    ]

    actor.private_knowledge = [
        "「裂隙灾变」发生时,我正带领一支巡逻队在尘烟裂谷区执行任务,我们进入时空裂隙后遭遇了一只巨大的机械魔物,整个队伍只有我幸存下来。",
        "裂隙医师协会的艾莉娅曾救过我一命,她用一种古老的精灵疗法治愈了我被瘴气毒素侵蚀的伤口,我对她充满感激。",
        "我对暗影信使没有好感,因为他们的错误信息才导致了我巡逻队的陷落,我发誓要找出并惩罚那个「千面」。",
        "奥露娜是我在巡逻中结识的法师,她的魔法帮助我击退了从裂隙中逃出的怪物,我们现在经常一起合作执行任务。",
    ]

    return actor
