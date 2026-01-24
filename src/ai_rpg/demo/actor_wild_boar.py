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
)


def create_actor_wild_boar() -> Actor:
    """
    创建野猪角色实例。

    野猪是桃花源周边山林中常见的野生动物，属于常物级别。
    它们性情凶猛，领地意识强，受到惊扰时会主动发起冲撞攻击。
    野猪皮毛、獠牙和肉质都是基础的狩猎素材，
    是猎人们初期练习狩猎技艺的理想目标。

    Returns:
        Actor: 野猪角色实例
    """
    wild_boar = create_actor(
        name="角色.常物.野猪",
        character_sheet=CharacterSheet(
            name="wild_boar",
            type=ActorType.ENEMY.value,
            profile="你是山林中的野猪，一种凶猛的野生动物。虽然平时以橡果、野菜和小动物为食，但性情暴躁，领地意识极强。当感到威胁时，你会毫不犹豫地低头冲撞，用锋利的獠牙撕咬敌人。你的皮厚肉粗，力量惊人，正面冲撞足以撞倒成年人。你不懂战术，只凭本能战斗，但野性的凶猛不容小觑。",
            base_body="",
            appearance="体型健壮的成年野猪，肩高约一米，体重超过两百斤。深褐色粗糙鬃毛覆盖全身，背部鬃毛竖立如刺。獠牙从嘴角伸出，长约十厘米，泛着象牙白的光泽。小眼睛透着凶光，鼻盘湿润有力。四肢粗短但肌肉发达，蹄子坚硬。身上沾着泥土和树皮碎屑，散发着野兽气味。",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # 定义野猪的技能
    wild_boar.skills = [
        BEAST_ATTACK_SKILL.model_copy(),
    ]

    return wild_boar
