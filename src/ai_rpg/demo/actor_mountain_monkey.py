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
    BEAST_ATTACK_SKILL,
    THROW_SKILL,
)


def create_actor_mountain_monkey() -> Actor:
    """
    创建山魈精怪角色实例。

    山魈是桃花源周边山林中常见的猴类精怪，属于精怪级别的中小型妖兽。
    它们机敏狡猾，擅长利用环境中的物体（石块、树枝等）作为武器，
    是猎人们常遇到的区域性挑战。

    Returns:
        Actor: 山魈精怪角色实例
    """
    mountain_monkey = create_actor(
        name="角色.精怪.山魈",
        character_sheet=CharacterSheet(
            name="mountain_monkey",
            type=ActorType.ENEMY.value,
            profile="你是山脉深处的山魈，一种介于野兽与精怪之间的猴类妖兽。长年栖息于古先民遗迹附近，因吸收遗迹残留的微弱灵气而变得异常机敏狡猾。你擅长利用周围环境作战，会捡起石块投掷，折断树枝挥舞。虽然单体实力不强，但你懂得观察猎人的破绽，寻找时机突袭。你对侵入领地者充满敌意。",
            base_body="",
            appearance="体型比普通猕猴略大的猴类精怪，灰褐色皮毛粗糙，背部和四肢有暗红色斑纹。琥珀色眼睛闪烁着狡猾灵性，尖利犬齿微露。手脚长满厚茧，爪子因攀岩而粗糙坚硬。身上无任何装备，附近散落着可作武器的石块和树枝。动作敏捷，时而四肢着地，时而直立观察。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # 定义山魈的技能
    mountain_monkey.skills = [
        THROW_SKILL.model_copy(),
        BEAST_ATTACK_SKILL.model_copy(),
    ]

    return mountain_monkey
