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
        stage_profile="你是一个阴暗潮湿的洞窟，墙壁上有会动的苔藓，地上没有一颗石头，全是杂草并且还会动。洞内还有哥布林的营地，地上散落着哥布林的粪便和食物残渣。洞穴深处传来低语声和偶尔的金属碰撞声，似乎有哥布林在进行某种活动。",
        actors=[],
    )


def create_demo_dungeon1() -> Dungeon:
    # 配置场景角色和属性
    actor_goblin = create_actor_goblin()
    actor_goblin.rpg_character_profile.hp = 1
    actor_goblin.kick_off_message += f"""\n注意:你非常狡猾，在遇到危险时会使用你的传家宝哥布林祭司的项链进入濒死状态，并在敌人放松警惕时以百分之十的血量复活并偷袭反击。但是这个项链只能使用一次，如果你再次遇到危险，你将无法使用它。项链属于装备，不会在卡牌中出现，濒死状态下会自动触发，不占用行动回合。"""

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
