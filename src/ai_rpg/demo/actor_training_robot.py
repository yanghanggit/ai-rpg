from ..models import (
    Actor,
    ActorCharacterSheet,
    ActorType,
    CharacterStats,
    Skill,
)
from .global_settings import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_SYSTEM_RULES,
)
from .utils import (
    create_actor,
)


def create_actor_training_robot() -> Actor:
    """
    创建一个训练机器人角色实例

    Returns:
        Actor: 训练机器人角色实例
    """
    training_robot = create_actor(
        name="角色.怪物.稻草人0号",
        character_sheet=ActorCharacterSheet(
            name="training_robot",
            type=ActorType.ENEMY.value,
            profile=f"""**历史**: 你是训练场的魔法构造体，由稻草人躯体和金属盔甲加固组成，内部嵌有符文核心维持基本战斗功能。
**性格**: 你遵循简单的战斗本能和基础攻防逻辑。
**禁忌**: 你惧怕火焰。""",
            base_body="",
            appearance=f"""稻草人形态的魔法构造体，人形体型，局部有金属盔甲加固。稻草填充的躯干外覆旧皮革，胸口和肩部装有简陋的金属护板。圆形稻草头颅，无明显面部特征，头部中央有微弱的符文光芒。手持一根磨损的木制训练棍。整体状态陈旧，稻草外露，金属部分有锈迹。""",
        ),
        # kick_off_message="",
        character_stats=CharacterStats(),
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        system_rules=FANTASY_WORLD_RPG_SYSTEM_RULES,
    )
    training_robot.skills = [
        Skill(
            name="使用武器",
            description="使用手中的武器或可触及的装备进行任意用途的行动，如攻击、防御、破坏、支撑、投掷等。使用方式和目标由实际场景决定。代价：如果攻击就会降低防御。",
        ),
    ]

    return training_robot
