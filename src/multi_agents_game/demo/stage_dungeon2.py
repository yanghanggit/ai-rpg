from ..models import (
    Dungeon,
)
from .demo_utils import (
    CAMPAIGN_SETTING,
    copy_stage,
)
from ..demo.stage_dungeon1 import stage_dungeon_cave1
from ..demo.actor_orc import actor_orcs


stage_dungeon_cave2 = copy_stage(
    name="场景.洞窟之二",
    stage_character_sheet=stage_dungeon_cave1.character_sheet,
    kick_off_message="",
    campaign_setting=CAMPAIGN_SETTING,
    actors=[],
)


def create_demo_dungeon2() -> Dungeon:

    stage_dungeon_cave2.actors = [actor_orcs]
    actor_orcs.rpg_character_profile.hp = 1

    return Dungeon(
        name="兽人洞窟",
        levels=[
            stage_dungeon_cave2,
        ],
    )
