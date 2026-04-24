from ..models import (
    Actor,
    Archetype,
    CharacterSheet,
    ActorType,
    CharacterStats,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
)
from .rpg_system_rules import (
    RPG_SYSTEM_RULES,
)
from .entity_factory import (
    create_actor,
)


def create_actor_sand_jackal() -> Actor:
    """
    创建沙豺角色实例。

    沙豺是活动于沙漠残垣外缘的常物级掠食者，
    昼伏夜出，以遗迹周边的小型生物为食。

    Returns:
        Actor: 沙豺角色实例
    """
    sand_jackal = create_actor(
        name="角色.怪物.沙豺",
        character_sheet=CharacterSheet(
            name="sand_jackal",
            type=ActorType.ENEMY,
            profile="""你是活动于沙漠残垣外缘的沙豺。白天你蜷缩在断壁的阴影下或埋入沙中静止不动，黄昏后才开始移动。你的嗅觉极为灵敏，能在数十步外察觉猎物的气息和震动。你不喜欢正面冲突，惯于绕到侧后方发动攻击，遇到强烈抵抗会迅速拉开距离。你的行动没有声音，脚掌宽大适合在松散沙地上奔跑。""",
            base_body="体型中等的犬科动物，四肢细长而有力，肩高约七十厘米。全身覆盖沙黄色短毛，背部有一道不规则的深色条纹。耳廓宽大直立，眼睛琥珀色，瞳孔在强光下收缩为细缝。口鼻部细长，牙齿洁白锋利。爪子宽而厚，趾间有蹼状连膜。尾巴粗且蓬松，尾尖颜色较深。身上没有多余的脂肪，肋骨轮廓在皮毛下隐约可见。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
        archetypes=[
            Archetype(
                description="纯攻击型：所有卡牌以最大化 damage_dealt 为目标，block_gain 始终为 0，affixes 留空；target_type 仅使用 enemy_single。"
            )
        ],
    )

    return sand_jackal
