"""副本实体销毁模块

负责销毁副本相关实体（敌人、场景）并重置副本数据，是 setup_dungeon 的逆操作。
"""

from loguru import logger
from ..game.dbg_game import DBGGame
from ..models import Dungeon


###################################################################################################################################################################
def teardown_dungeon(dbg_game: DBGGame, dungeon: Dungeon) -> None:
    """销毁副本相关实体并重置副本数据，是 setup_dungeon 的逆操作。"""

    logger.debug(f"[teardown_dungeon] 开始清理副本实体: dungeon={dungeon.name!r}")

    # 1. 销毁所有副本中的 actor 实体
    for room in dungeon.rooms:
        for actor in room.stage.actors:
            destroy_actor_entity = dbg_game.get_actor_entity(actor.name)
            if destroy_actor_entity is not None:
                dbg_game.destroy_entity(destroy_actor_entity)

    # 2. 销毁所有副本中的 stage 实体
    for room in dungeon.rooms:
        destroy_stage_entity = dbg_game.get_stage_entity(room.stage.name)
        if destroy_stage_entity is not None:
            dbg_game.destroy_entity(destroy_stage_entity)

    # 3. 重置副本数据为空副本
    dbg_game._world.dungeon = Dungeon(name="", rooms=[], premise="")

    # 4. 打印副本销毁完成日志
    logger.debug("[teardown_dungeon] 副本实体清理完成，dungeon 已重置")
