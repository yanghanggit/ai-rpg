"""
沙漠遗迹地下城副本工厂模块
"""

from ..models import (
    Dungeon,
    CombatRoom,
    StageProfile,
    StageType,
    RPG_SYSTEM_RULES,
    Actor,
    CharacterSheet,
    ActorType,
    CharacterStats,
    create_actor,
    create_stage,
)
from .settings import (
    CAMPAIGN_SETTING,
)


########################################################################################################################
def create_actor_sand_jackal() -> Actor:
    """
    创建沙豺角色实例。
    """
    sand_jackal = create_actor(
        name="怪物.沙豺",
        character_sheet=CharacterSheet(
            name="sand_jackal",
            type=ActorType.MONSTER,
            profile="""你是活动于沙漠残垣外缘的沙豺。白天你蜷缩在断壁的阴影下或埋入沙中静止不动，黄昏后才开始移动。你的嗅觉极为灵敏，能在数十步外察觉猎物的气息和震动。你不喜欢正面冲突，惯于绕到侧后方发动攻击，遇到强烈抵抗会迅速拉开距离。你的行动没有声音，脚掌宽大适合在松散沙地上奔跑。""",
            base_body="体型中等的犬科动物，四肢细长而有力，肩高约七十厘米。全身覆盖沙黄色短毛，背部有一道不规则的深色条纹。耳廓宽大直立，眼睛琥珀色，瞳孔在强光下收缩为细缝。口鼻部细长，牙齿洁白锋利。爪子宽而厚，趾间有蹼状连膜。尾巴粗且蓬松，尾尖颜色较深。身上没有多余的脂肪，肋骨轮廓在皮毛下隐约可见。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        keywords=[
            "纯攻击型：每张卡牌专注于对单个敌人造成直接伤害，不携带任何附加效果或持续状态。骰值 0-30 为失败，攻击乏力、伤害偏低；骰值 31-70 为正常，伤害稳定适中；骰值 71-100 为优质，体现爆发感，伤害显著高于角色基础攻击力。"
        ],
    )

    return sand_jackal


########################################################################################################################
def create_sand_jackal_ruins_dungeon() -> Dungeon:
    """
    创建沙豺遗迹副本。
    """
    stage_ruins_outskirts = create_stage(
        name="场景.残柱外沿",
        stage_profile=StageProfile(
            name="ruins_outskirts",
            type=StageType.DUNGEON,
            profile="""你是沙漠残垣遗迹外缘的开阔地带，几根已倒塌或半倒的断柱散落在沙地上，截面朝向各异。
地面是松软的沙土与裸露的岩板交替分布，风在断柱之间卷起低矮的沙尘旋涡。柱身背风侧积着细沙，风向一侧则磨蚀痕迹明显。
日落前后，气温迅速下降，沙面在余光中反射出橙红色调。断柱投下长而倾斜的阴影，阴影边缘处沙土颜色明显更暗。""",
        ),
        campaign_setting=CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    actor_wolf = create_actor_sand_jackal()
    stage_ruins_outskirts.actors = [actor_wolf]

    return Dungeon(
        name="地下城.沙漠残垣",
        ecology="遗迹外缘散落的断柱与沙地交界处。松软沙土上留有大量宽爪印迹，深浅不一，部分印迹已被风沙半掩。断柱根部背风侧有浅凹，沙面压实，是沙豺白天蜷伏的痕迹。偶尔可见被咬断的小型骨骼碎片半埋在沙中。",
        rooms=[
            CombatRoom(stage=stage_ruins_outskirts),
        ],
    )
