from ..models import (
    Actor,
    ActorType,
    CharacterStats,
    Skill,
)
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
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
        name="角色.怪物.训练稻草人001号",
        character_sheet_name="training_robot",
        kick_off_message="",
        character_stats=CharacterStats(base_dexterity=1),
        type=ActorType.ENEMY,
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        actor_profile=f"""**历史**: 你是训练场的魔法构造体，由稻草人躯体和金属盔甲加固组成，内部嵌有符文核心维持基本战斗功能。
**性格**: 你遵循简单的战斗本能和基础攻防逻辑。
**禁忌**: 你惧怕火焰。""",
        appearance=f"""稻草人形态的魔法构造体，人形体型，局部有金属盔甲加固。稻草填充的躯干外覆旧皮革，胸口和肩部装有简陋的金属护板。圆形稻草头颅，无明显面部特征，头部中央有微弱的符文光芒。手持一根磨损的木制训练棍。整体状态陈旧，稻草外露，金属部分有锈迹。""",
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )
    training_robot.skills = [
        Skill(
            name="稻草挥打",
            description="用身上的武器进行挥打，造成基础物理伤害。攻击后需要复位，动作缓慢，降低防御力。",
        ),
        Skill(
            name="稻草防御",
            description="用身上的护甲进行防御，减少所受物理伤害。防御后需要调整，动作缓慢，降低攻击力。",
        ),
    ]

    return training_robot
