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
            profile=f"""**历史**: 你是猎人备物所外训练场的木桩人偶，由村中匠人用坚实的楠木和竹条编制而成，内部填充稻草，外层包裹兽皮增加韧性。历代猎人学徒都在你身上磨练技艺。
**性格**: 你是无生命的训练器械，被动承受攻击，偶尔因结构松动而倾斜或摇晃。
**禁忌**: 你作为木制品最怕火焰。""",
            base_body="人形木桩，约成年男子高度，由竹木框架撑起轮廓，稻草填充躯干，外裹旧兽皮。关节处用麻绳捆扎，底部插入地面的木桩固定。表面布满刀剑留下的痕迹和箭矢射穿的孔洞。",
            appearance=f"""朴素的人形训练木桩，以粗壮的楠木为主干，竹条编织成四肢框架，内部塞满稻草。躯干外层包裹着磨损的旧兽皮，胸口和肩部已被无数次攻击打得斑驳。圆形稻草头颅简单扎成，用炭笔画着粗略的五官标记。一只"手臂"上绑着破旧的木盾残片，另一只手固定着磨秃的木棍。整体状态陈旧，稻草时有外露，兽皮多处开裂，但结构依然牢固。底部粗木桩深深插入训练场的泥土中。""",
        ),
        character_stats=CharacterStats(),
        campaign_setting=RPG_CAMPAIGN_SETTING,
        system_rules=RPG_SYSTEM_RULES,
    )

    # 定义训练木桩的技能
    actor.skills = [
        Skill(
            name="使用武器",
            description="使用手中的武器或可触及的装备进行任意用途的行动，如攻击、防御、破坏、支撑、投掷等。使用方式和目标由实际场景决定。代价：如果攻击就会降低防御。",
        ),
    ]

    return actor
