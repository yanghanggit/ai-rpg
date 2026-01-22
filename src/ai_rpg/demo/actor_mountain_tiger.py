from ..models import (
    Actor,
    CharacterSheet,
    ActorType,
    CharacterStats,
)
from .global_settings import (
    RPG_CAMPAIGN_SETTING,
    RPG_SYSTEM_RULES,
)
from .entity_factory import (
    create_actor,
)
from .common_skills import (
    BEAST_ATTACK_SKILL,
    INTIMIDATION_SKILL,
    # THROW_SKILL,
)


def create_actor_mountain_tiger() -> Actor:
    """
    创建山中虎妖角色实例。

    山中虎妖是桃花源周边山林中的大妖级别妖兽，位于生态链顶端。
    它们体型巨大，力量惊人，领地意识极强，是生态的调节者。
    其存在可能与古先民的某种"设计"或"封印"相关。

    Returns:
        Actor: 山中虎妖角色实例
    """
    mountain_tiger = create_actor(
        name="角色.大妖.山中虎",
        character_sheet=CharacterSheet(
            name="mountain_tiger",
            type=ActorType.ENEMY.value,
            profile="你是山脉深处的山中虎妖，大妖级别的妖兽，生态链的顶点。你的领地横跨数十里山林，世代守护着一处古先民遗迹。长年吸收遗迹溢出的浓厚灵气，你的身躯远超寻常猛虎，皮毛坚韧如铁，力量足以撼动巨石。你对领地内的一切生灵有绝对掌控，能凭借气息判断入侵者的强弱。你既是猎手，也是山林秩序的执行者，对破坏生态平衡者绝不容忍。",
            base_body="",
            appearance="体型巨大的虎类妖兽，肩高近两米，体长超过四米。黑黄相间的皮毛泛着金属般的光泽，虎纹粗犷刚硬。额头正中有一道不规则的暗红色印记，隐约呈现古老符文的形状。琥珀色的双瞳深邃而威严，獠牙粗长锋利。四肢粗壮有力，爪子如钩，每一步踏地都带来沉重的压迫感。周身隐约环绕着淡淡的灵气波动。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # 定义山中虎妖的技能
    mountain_tiger.skills = [
        # INTIMIDATION_SKILL.model_copy(),
        BEAST_ATTACK_SKILL.model_copy(),
    ]

    return mountain_tiger
