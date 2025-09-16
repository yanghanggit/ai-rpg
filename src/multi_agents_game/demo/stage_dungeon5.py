from .actor_training_robot import create_actor_training_robot
from ..models import Dungeon, Stage, StageType
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .utils import (
    create_stage,
)


def create_stage_cave5() -> Stage:
    """
    创建一个训练场场景实例

    Returns:
        Stage: 训练场场景实例
    """
    return create_stage(
        name="场景.训练场",
        character_sheet_name="training_ground",
        kick_off_message="",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.DUNGEON,
        stage_profile="你是一个用来测试技能和战斗策略的训练场，训练场里有干草和木桩，地型被改造成了沼泽，所以训练场里也充满了沼气和水，地上还插着生锈的剑和各种生物的白骨来营造气氛。",
        actors=[],
    )


def create_demo_dungeon5() -> Dungeon:

    actor_training_robot = create_actor_training_robot()
    actor_training_robot.rpg_character_profile.hp = 10
    actor_training_robot.kick_off_message += f"""\n注意：你作为一个训练机器人只会最基本的攻击和防御技能，但是你死不掉。你有‘无限生命’，每个回合结束时都会回满至Max_HP，这是一个status_effects，战斗开始后就会生效，rounds=999。"""

    stage_cave5 = create_stage_cave5()
    stage_cave5.actors = [actor_training_robot]

    return Dungeon(
        name="训练场",
        levels=[
            stage_cave5,
        ],
    )
