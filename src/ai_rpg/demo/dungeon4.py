from ..models import (
    Dungeon,
)
from .actor_goblin import create_actor_goblin
from .actor_orc import create_actor_orc
from .dungeon1 import create_stage_cave1
from .dungeon2 import create_stage_cave2


def create_demo_dungeon4() -> Dungeon:

    # 创建两个洞窟场景
    stage_cave1 = create_stage_cave1()
    actor_goblin = create_actor_goblin()
    actor_goblin.character_stats.hp = 1
    stage_cave1.actors = [actor_goblin]

    # 创建第二个洞窟场景
    stage_cave2 = create_stage_cave2()
    actor_orc = create_actor_orc()
    actor_orc.character_stats.hp = 1
    stage_cave2.actors = [actor_orc]

    return Dungeon(
        name="哥布林与兽人",
        stages=[
            stage_cave1,
            stage_cave2,
        ],
    )
