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
    WEAPON_DEFEND_SKILL,
)


def create_training_dummy() -> Actor:
    """
    创建一个训练木桩角色实例。

    这是桃花源猎人们用于日常训练的简易木桩人偶，
    由竹木框架和稻草填充制成，用于练习武器技巧和战斗反应。

    Returns:
        Actor: 训练木桩角色实例
    """
    actor = create_actor(
        name="角色.训练木桩",
        character_sheet=CharacterSheet(
            name="training_dummy",
            type=ActorType.ENEMY.value,
            profile=f"""**历史**: 你是猎人备物所外训练场的特殊木桩人偶，本体由青木妖心节（建木妖力结晶）构成，外层包裹竹条框架和兽皮伪装。历代猎人学徒都在你身上磨练技艺，但无人知晓你的真正本质。
**性格**: 你是拥有妖力的训练器械，被动承受攻击。无论受到何种伤害，你都会因青木妖心节的不死特性而重生。
**禁忌**: 你的青木妖心节本质使你对妖力克制类法术格外敏感。""",
            base_body="人形木桩，约成年男子高度，外观是竹木框架和稻草填充，但本体实际由青木妖心节构成。外层包裹旧兽皮作为伪装，关节处用麻绳捆扎，底部插入地面固定。",
            appearance=f"""朴素的人形训练木桩，表面看似以粗壮的楠木为主干，竹条编织成四肢框架，内部塞满稻草。躯干外层包裹着磨损的旧兽皮，胸口和肩部已被无数次攻击打得斑驳。圆形稻草头颅简单扎成，用炭笔画着粗略的五官标记。一只"手臂"上绑着破旧的木盾残片，另一只手固定着磨秃的木棍。整体状态陈旧，稻草时有外露，兽皮多处开裂，但结构依然牢固。底部粗木桩深深插入训练场的泥土中。然而，若仔细观察，偶尔能从破损处瞥见内部隐约的翠绿光泽。""",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # 定义训练木桩的技能
    actor.skills = [
        # WEAPON_ATTACK_SKILL.model_copy(),
        WEAPON_DEFEND_SKILL.model_copy(),
    ]

    return actor
