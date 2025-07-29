from ..models import Dungeon, StageType, Stage
from .demo_utils import (
    CAMPAIGN_SETTING,
    create_stage,
)
from ..demo.actor_orc import create_actor_orc


def create_stage_cave2() -> Stage:
    """
    创建一个兽人洞窟场景实例

    Returns:
        Stage: 兽人洞窟场景实例
    """
    return create_stage(
        name="场景.洞窟之二",
        character_sheet_name="goblin_cave",
        kick_off_message="",
        campaign_setting=CAMPAIGN_SETTING,
        type=StageType.DUNGEON,
        stage_profile="你是一个阴暗潮湿的洞窟，四周布满了苔藓和石笋。洞内有哥布林的营地，地上散落着破旧的武器和食物残渣。洞穴深处传来低语声和偶尔的金属碰撞声，似乎有哥布林在进行某种活动。",
        actors=[],
    )


def create_demo_dungeon2() -> Dungeon:

    actor_orc = create_actor_orc()
    actor_orc.rpg_character_profile.hp = 1

    stage_cave2 = create_stage_cave2()
    stage_cave2.actors = [actor_orc]

    return Dungeon(
        name="兽人洞窟",
        levels=[
            stage_cave2,
        ],
    )
