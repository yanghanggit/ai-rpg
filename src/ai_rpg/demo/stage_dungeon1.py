from .actor_goblin import create_actor_goblin
from ..models import (
    Dungeon,
    StageType,
)
from ..models.objects import Stage
from .campaign_setting import (
    FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
    FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
)
from .utils import (
    create_stage,
)


def create_stage_cave1() -> Stage:

    return create_stage(
        name="场景.洞窟之一",
        character_sheet_name="goblin_cave",
        kick_off_message="",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.DUNGEON,
        stage_profile="你是一个黑暗干燥的洞窟，地上都是易燃的干草，墙上插着各种箭矢，地上还有破损的盔甲和断剑。洞窟深处似乎有哥布林在进行某种活动。",
        actors=[],
        global_game_mechanics=FANTASY_WORLD_RPG_GLOBAL_GAME_MECHANICS,
    )


def create_demo_dungeon1() -> Dungeon:
    # 配置场景角色和属性
    actor_goblin = create_actor_goblin()
    actor_goblin.rpg_character_profile.hp = 1
    # actor_goblin.kick_off_message += f"""\n注意:你非常狡猾，所以身上带了一件哥布林的传家宝项链用来保命，这个项链会让你在死亡时以百分之十的血量复活，并且复活后的第一次攻击会造成双倍伤害。但是这个项链只能让你复活一次。项链属于一种状态效果，不触发时会一直存在，不会在卡牌中出现，死亡时会自动触发，并且状态效果会消失。不受负面效果影响，不占用行动回合。"""
    actor_goblin.kick_off_message += f"""\n注意:你在战斗中会优先攻击法师和弓箭手等远程职业，因为他们对你威胁最大。如果没有远程职业，你会优先攻击血量最低的敌人。"""
    # 创建洞窟场景
    stage_cave1 = create_stage_cave1()
    stage_cave1.actors = [actor_goblin]

    # 添加哥布林角色到洞窟场景
    return Dungeon(
        name="哥布林洞窟",
        stages=[
            stage_cave1,
        ],
    )
