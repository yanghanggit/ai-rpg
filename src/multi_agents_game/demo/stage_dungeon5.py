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
        stage_profile="你是一个用来测试技能和战斗策略的训练场，训练场里有各种可以利用的环境物体。",
        actors=[],
    )


def create_demo_dungeon5() -> Dungeon:

    actor_training_robot = create_actor_training_robot()
    actor_training_robot.rpg_character_profile.hp = 1
    actor_training_robot.kick_off_message += f"""\n注意：你作为一个训练机器人不会攻击，不会死亡，你不使用技能生成的功能，因为你只会生成防御技能，并且每回合结束都会回满血量"""

    stage_cave5 = create_stage_cave5()
    stage_cave5.actors = [actor_training_robot]

    return Dungeon(
        name="训练场",
        levels=[
            stage_cave5,
        ],
    )
