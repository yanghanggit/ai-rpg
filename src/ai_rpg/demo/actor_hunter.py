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
    WEAPON_ATTACK_SKILL,
    WEAPON_DEFEND_SKILL,
    UNARMED_COMBAT_SKILL,
)


def create_hunter() -> Actor:
    """
    创建一个避秦之民猎人角色实例（石坚）。

    该角色是桃花源中石氏猎人家族的传人，专职狩猎妖兽、维护生态平衡。
    他经历过古先民遗迹的神秘，见识过山魈与精怪的凶险，是村落与山林之间的守护者。

    Returns:
        Actor: 猎人角色实例，包含完整的角色属性、技能和背景设定
    """
    actor = create_actor(
        name="角色.猎人.石坚",
        character_sheet=CharacterSheet(
            name="hunter_shi",
            type=ActorType.ALLY,
            profile=f"""**历史**: 你是避秦之民的后裔，石氏猎人家族的第十三代传人。自幼随父辈学习狩猎技艺，熟知桃花源周边山林的每一条兽径与水源。你曾深入山脉深处追踪一只伤人的山魈，误入古先民遗迹，目睹了那些无法理解的石刻符文与奇异光华。在与窃脂精怪的搏斗中，你凭借祖传的陷阱技艺与对山林的熟稔幸存下来，但也因此见识到了这片土地隐藏的更深秘密。你深知维护生态平衡的重要，既是村落的守护者，也是山林妖兽与人类之间的调停者。
**性格**: 你性格沉稳内敛，行事谨慎而果决，深谙山林生存之道。你尊重自然，但也明白有时必须以狩猎来维持平衡。
**禁忌**: 你深恶痛绝滥猎妖兽、破坏山林生态平衡之举，以及贪图古先民遗迹之力而不知敬畏者。
**最爱**: 你最爱桃花酒配野味干肉，以及在月下于桃林边缘巡视时的宁静。""",
            base_body="年近三十的男子，身形精悍灵活，常年山林狩猎练就的结实肌肉。肤色因风吹日晒而呈健康的褐色。眼神沉静警觉，蓄有短须，发髻简单束起。左肩有被山魈利爪留下的三道疤痕，右手虎口处有长年握持弓弦磨出的老茧。",
            appearance="",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    actor.skills = [
        WEAPON_ATTACK_SKILL.model_copy(),
        WEAPON_DEFEND_SKILL.model_copy(),
        UNARMED_COMBAT_SKILL.model_copy(),
    ]

    return actor
