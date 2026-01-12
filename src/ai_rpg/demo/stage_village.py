"""
桃花源村落场景模块。

本模块定义了《桃花源记》世界观中村落内的四个核心场景：
1. 猎人备物所 - 猎人们整备装备、补给物资的专属空间
2. 村中议事堂 - 村民聚会交流、分享情报的公共场所
3. 石氏木屋 - 石氏猎人家族祖宅，玩家专属的特殊场景，拥有神秘铜镜
4. 猎人训练场 - 猎人学徒和猎人们日常训练技艺的开放场地

这些场景构成了避秦之民在桃花源中的日常生活与狩猎准备的核心空间。
"""

from ..models import Stage, StageProfile, StageType
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
    RPG_COMBAT_MECHANICS,
)
from .utils import (
    create_stage,
)


def create_hunter_storage() -> Stage:
    """
    创建猎人备物所场景实例。

    这是桃花源村落中猎人们的专属整备空间，位于靠近山林的坚实石屋内。
    猎人们在此整备由妖兽素材制成的武器装备，补充草药与干粮，
    为深入山林狩猎妖兽做好充分准备。

    Returns:
        Stage: 猎人备物所场景实例，提供装备整备与物资补给功能
    """

    return create_stage(
        name="场景.猎人备物所",
        stage_profile=StageProfile(
            name="hunter_storage",
            type=StageType.HOME,
            profile="""你是桃花源村落中的猎人备物所，位于村子靠近山林一侧的坚实石屋内。
屋内墙壁悬挂着各式由妖兽素材制成的弓弩、长矛与短刃，角落整齐码放着兽筋编织的护具、草药包与干粮袋。
空气中混杂着兽皮的麝香、竹木的清香与草药的苦味。""",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )


def create_village_hall() -> Stage:
    """
    创建村中议事堂场景实例。

    这是桃花源村落中心的公共场所，既是村民聚餐的温馨空间，
    也是情报交流的枢纽。猎人们在此分享狩猎经验，长者讲述避秦先祖的历史，
    年轻人交换关于妖兽活动与古先民遗迹的最新情报。墙上的山林地图记录着
    村落周边的危险与机遇。

    Returns:
        Stage: 村中议事堂场景实例，提供社交互动与情报交流功能
    """

    return create_stage(
        name="场景.村中议事堂",
        stage_profile=StageProfile(
            name="village_hall",
            type=StageType.HOME,
            profile="""你是桃花源村落中心的议事堂，也是村民们聚餐交流的公共场所。
宽敞的木制厅堂内摆放着数张长条木桌，桌上常备桃花酿与野味。墙上悬挂着手绘的山林地图，标注着近期发现的妖兽踪迹与古先民遗迹位置。
空气中飘散着桃花酒的清香与炖肉的醇厚香气。""",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )


# TODO: 石氏木屋只能玩家进入，其他盟友不能进入
def create_shi_family_house() -> Stage:
    """
    创建石氏木屋场景实例（玩家专属）。

    这是石氏猎人家族的祖宅，位于桃花林边缘的古朴木屋。
    屋内最特别的是一面从古先民遗迹带回的神秘铜镜，能够映照出桃花源内外的
    各处景象。只有石氏血脉的继承人（玩家控制的角色）能够独自进入此屋，
    并借由铜镜之力观察和穿行于各个场景。

    Note:
        这是特殊的玩家专属场景，其他盟友角色无法进入。

    Returns:
        Stage: 石氏木屋场景实例，提供场景观察与穿梭功能
    """

    return create_stage(
        name="场景.石氏木屋",
        stage_profile=StageProfile(
            name="shi_family_house",
            type=StageType.HOME,
            profile="你是石氏猎人家族的祖宅，一座位于桃花林边缘的古朴木屋。屋内陈设简朴，正中悬挂着历代石氏猎人的木牌位。最特别的是靠墙的一面古旧铜镜，镜面常年笼罩着微光——这是石氏先祖从古先民遗迹中带回的神秘之物，据说能映照出桃花源内外的各处景象。",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )


def create_training_ground() -> Stage:
    """
    创建猎人训练场场景实例。

    这是桃花源村落中猎人们日常训练的开放场地，位于猎人备物所旁的空地上。
    学徒们在此磨练武器技巧，老猎人们传授狩猎经验，训练木桩、箭靶和
    各种训练器械散布其中。这里是猎人技艺传承的重要场所。

    Returns:
        Stage: 猎人训练场场景实例，提供战斗训练与技能磨练功能
    """

    return create_stage(
        name="场景.猎人训练场",
        stage_profile=StageProfile(
            name="training_ground",
            type=StageType.DUNGEON,
            profile="""你是桃花源村落中的猎人训练场，位于猎人备物所旁的开阔空地上。
场地以夯实的黄土为地面，四周立着简易的竹木栅栏。场内散布着多个训练木桩，有的已被打得摇摇欲坠，有的刚刚由村中匠人修缮完毕。场地一侧竖立着数排草编箭靶，靶心处密布箭痕。另一侧摆放着石锁、木桩等力量训练器械。""",
        ),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        combat_mechanics=RPG_COMBAT_MECHANICS,
    )
