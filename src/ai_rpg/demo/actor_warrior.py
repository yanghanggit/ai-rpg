from ..models import (
    Actor,
    ActorType,
    CharacterStats,
    SkillBookComponent,
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
        skills_book=SkillBookComponent(
            name="战士技能书",
            skills=[
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
                    name="剑刃过载",
                    description="激活背负的高频振动长剑的过载模式，对敌人护甲造成毁灭性的切割伤害。但过载会导致武器过热，下一回合无法使用该武器，且手臂因剧烈震动而暂时麻木，命中率下降。",
                ),
                Skill(
                    name="古弩压制",
                    description="使用古老精密的能源弩进行快速连射，压制敌人的行动，使其难以移动或反击。但古老的机械结构容易卡壳，使用后需要花费时间重新校准，下一回合无法进行远程攻击。",
                ),
                Skill(
                    name="力场盾击",
                    description="激活左臂的能量力场便携盾牌，释放储存的能量猛击敌人，造成冲击伤害并击退目标。但释放能量会耗尽盾牌的储备，导致盾牌在一段时间内失效，自身防御力显著降低。",
                ),
                Skill(
                    name="晶痕共鸣",
                    description="引导右臂能量爪留下的晶体化疤痕中的残留能量，释放出一道强力的能量波攻击敌人。但强行引导异变能量会引发剧烈疼痛，并唤起对“地脉扰劫”的创伤记忆，造成自身精神动摇，受到精神伤害增加。",
                ),
            ]
        )
    )
