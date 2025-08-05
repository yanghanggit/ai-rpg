from ..models.objects import Stage
from ..models import (
    StageType,
    Dungeon,
)
from .utils import (
    create_stage,
)
from ..demo.actor_goblin import create_actor_goblin
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING


def create_stage_cave1() -> Stage:

    return create_stage(
        name="场景.洞窟之一",
        character_sheet_name="goblin_cave",
        kick_off_message="",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.DUNGEON,
        stage_profile="你是一个阴暗潮湿的洞窟，四周布满了苔藓和石笋。洞内有哥布林的营地，地上散落着破旧的武器和食物残渣。洞穴深处传来低语声和偶尔的金属碰撞声，似乎有哥布林在进行某种活动。",
        actors=[],
    )


def create_demo_dungeon1() -> Dungeon:
    # 配置场景角色和属性
    actor_goblin = create_actor_goblin()
    actor_goblin.rpg_character_profile.hp = 1

    # 创建洞窟场景
    stage_cave1 = create_stage_cave1()
    stage_cave1.actors = [actor_goblin]

    # 添加哥布林角色到洞窟场景
    return Dungeon(
        name="哥布林洞窟",
        levels=[
            stage_cave1,
        ],
    )
