from .actor_training_robot import create_actor_training_robot
from ..models import Dungeon, Stage, StageType, Item, ItemType
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
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
        stage_profile="你是一个用来测试战斗策略的训练场，训练场里有干草和木桩，地型被改造成了沼泽，所以训练场里也充满了沼气和水，地上还插着生锈的剑和各种生物的白骨来营造气氛。",
        actors=[],
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )


def create_demo_dungeon5() -> Dungeon:

    actor_training_robot = create_actor_training_robot()
    actor_training_robot.character_stats.hp = 10
    actor_training_robot.kick_off_message += (
        f"""\n注意：你作为一个训练机器人只会最基本的攻击和防御。"""
    )
    actor_training_robot.inventory.items.append(
        Item(
            name="传奇道具.钢铁之心",
            uuid="",
            type=ItemType.UNIQUE_ITEM,
            description="此道具让你拥有无限生命! 即：每个战斗回合在生成行动与更新状态时，都会将生命恢复到你的Max_HP。如果你还没有'钢铁之心'相关的status_effect，则在第一次更新状态时创建一个，标记此道具的存在，duration=999。后续回合系统会自动维护此状态效果，无需重复创建。而且在战斗中如果你的生命值降到0，你不会死掉，而是会周身冒烟并坚挺地站立着，等待下一个回合的开始。",
        )
    )

    stage_cave5 = create_stage_cave5()
    stage_cave5.actors = [actor_training_robot]

    return Dungeon(
        name="训练场",
        stages=[
            stage_cave5,
        ],
    )
