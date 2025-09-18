from .actor_goblin import create_actor_goblin
from .actor_orc import create_actor_orc
from ..models import Dungeon, Stage, StageType
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .utils import (
    create_stage,
)

# from ai_rpg.demo import actor_goblin


def create_stage_cave6() -> Stage:
    """
    创建一个洞窟场景实例

    Returns:
        Stage: 洞窟场景实例
    """
    return create_stage(
        name="场景.洞窟之四",
        character_sheet_name="goblin_and_orc_cave",
        kick_off_message="",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.DUNGEON,
        stage_profile="你是一个黑暗干燥的古代科技遗迹，地上都是散落的机械零件，还有许多罐子和从罐子里流出的不明液体，看起来似乎和油一样易燃。墙壁上还有许多暴露出来的电子元件，有的甚至还在冒着电流。遗迹中不时还能看到一些闪烁的光点，那是古代科技遗留下来的老旧机器人，虽然时间久远，但仍然具有威胁。遗迹深处传来说话的声音，似乎有人在争吵。",
        actors=[],
    )


def create_demo_dungeon6() -> Dungeon:

    actor_goblin = create_actor_goblin()
    actor_goblin.rpg_character_profile.hp = 50
    actor_goblin.kick_off_message += f"""\n注意：你非常狡猾，所以身上带了一件哥布林的传家宝项链用来保命，这个项链会让你在死亡时以百分之十的血量复活，并且复活后的第一次攻击会造成双倍伤害。但是这个项链只能让你复活一次。项链属于status_effects，duration=999，战斗开始时就会存在，死亡时会自动触发，触发后消失，不受负面效果影响，不占用行动回合。"""

    actor_orc = create_actor_orc()
    actor_orc.rpg_character_profile.hp = 5

    stage_cave6 = create_stage_cave6()
    stage_cave6.actors = [actor_goblin, actor_orc]

    return Dungeon(
        name="哥布林和兽人洞窟",
        levels=[
            stage_cave6,
        ],
    )
