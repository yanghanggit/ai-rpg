from ..models import (
    Dungeon,
)
from .stage_dungeon1 import create_stage_cave1
from .stage_dungeon2 import create_stage_cave2
from .actor_goblin import create_actor_goblin
from .actor_orc import create_actor_orc


def create_demo_dungeon4() -> Dungeon:

    # 创建两个洞窟场景
    stage_cave1 = create_stage_cave1()
    actor_goblin = create_actor_goblin()
    actor_goblin.rpg_character_profile.hp = 1
    stage_cave1.actors = [actor_goblin]

    # 创建第二个洞窟场景
    actor_orc = create_actor_orc()
    actor_orc.rpg_character_profile.hp = 1
    stage_cave2 = create_stage_cave2()
    stage_cave2.actors = [actor_orc]

    return Dungeon(
        name="哥布林与兽人",
        levels=[
            stage_cave1,
            stage_cave2,
        ],
    )
