from ..demo.actor_slime import create_actor_slime
from ..models import Dungeon, Stage, StageType
from .campaign_setting import FANTASY_WORLD_RPG_CAMPAIGN_SETTING
from .utils import (
    create_stage,
)


def create_stage_cave5() -> Stage:
    """
    创建一个史莱姆洞窟场景实例

    Returns:
        Stage: 史莱姆洞窟场景实例
    """
    return create_stage(
        name="场景.洞窟之五",
        character_sheet_name="slime_cave",
        kick_off_message="",
        campaign_setting=FANTASY_WORLD_RPG_CAMPAIGN_SETTING,
        type=StageType.DUNGEON,
        stage_profile="你是一个阴暗潮湿的洞窟，洞窟内是一片沼泽，沼泽中杂草丛生，水也漫过了脚踝。透过水面能看见沼泽中还有很多不知名的生物死亡后留下的白骨",
        actors=[],
    )


def create_demo_dungeon5() -> Dungeon:

    actor_slime = create_actor_slime()
    actor_slime.rpg_character_profile.hp = 1

    stage_cave5 = create_stage_cave5()
    stage_cave5.actors = [actor_slime]

    return Dungeon(
        name="史莱姆洞窟",
        levels=[
            stage_cave5,
        ],
    )
