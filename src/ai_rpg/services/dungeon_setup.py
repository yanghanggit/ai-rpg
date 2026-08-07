"""
副本实体创建与销毁模块

负责根据副本模型创建游戏实体（敌人、场景），以及退出副本时销毁这些实体。
setup_dungeon 与 teardown_dungeon 互为逆操作。
"""

from typing import Tuple
from loguru import logger
from ..game.config import DUNGEONS_DIR
from ..game.dbg_game import DBGGame
from ..models import (
    ActorType,
    Dungeon,
    StageType,
)


###################################################################################################################################################################
def setup_dungeon(dbg_game: DBGGame, dungeon_name: str) -> Tuple[bool, str]:
    """从文件加载副本数据、赋值到游戏世界，并创建全部游戏实体（敌人和场景）。（幂等）"""
    # 1. 校验名称并加载文件
    if not dungeon_name:
        error_msg = "setup_dungeon 失败: dungeon_name 为空"
        logger.error(error_msg)
        return False, error_msg

    dungeon_path = DUNGEONS_DIR / f"{dungeon_name}.json"
    if not dungeon_path.exists():
        error_msg = f"setup_dungeon 失败: 副本文件不存在 {dungeon_path}"
        logger.error(error_msg)
        return False, error_msg

    dungeon = Dungeon.model_validate_json(dungeon_path.read_text(encoding="utf-8"))

    if len(dungeon.rooms) == 0:
        error_msg = f"setup_dungeon 失败: {dungeon.name} 没有关卡数据"
        logger.error(error_msg)
        return False, error_msg

    # 守护：当前游戏世界中已有副本正在进行，不允许重新 setup
    if dbg_game._world.dungeon.current_room_index >= 0:
        error_msg = (
            f"setup_dungeon 失败: 当前副本 {dbg_game._world.dungeon.name!r} 正在进行中 "
            f"(current_room_index={dbg_game._world.dungeon.current_room_index})，请先退出"
        )
        logger.error(error_msg)
        return False, error_msg

    assert (
        not dbg_game.is_player_in_dungeon_stage
    ), "setup_dungeon 失败: 玩家已在副本场景中！"

    # 2. 赋值到游戏世界（此后 dbg_game.current_dungeon 指向新加载的实例）
    dbg_game._world.dungeon = dungeon
    logger.debug(f"setup_dungeon: 已将 {dungeon.name} 赋值到 world.dungeon")

    # 3. 幂等：实体已创建则跳过
    if dungeon.setup_entities:
        logger.debug(f"setup_dungeon: {dungeon.name} 实体已创建，跳过")
        return True, f"副本实体已存在，跳过创建: {dungeon.name}"

    # 4. 验证：所有 actor 必须是 MONSTER 类型
    for room in dungeon.rooms:
        for actor in room.stage.actors:
            actor_entity = dbg_game.get_actor_entity(actor.name)
            assert actor_entity is None, "actor_entity is not None"
            assert (
                actor.character_sheet.type == ActorType.MONSTER
            ), "actor_entity is not enemy type"

    # 5. 验证：所有关卡场景必须是 DUNGEON 类型
    for room in dungeon.rooms:
        stage_entity = dbg_game.get_stage_entity(room.stage.name)
        assert stage_entity is None, "stage_entity is not None"
        assert (
            room.stage.stage_profile.type == StageType.DUNGEON
        ), "stage_entity is not dungeon type"

    # 6. 创建副本实体（敌人和关卡场景）
    logger.debug(f"正在根据副本模型创建实体: {dungeon.name}")
    dbg_game.create_actor_entities(
        [actor for room in dungeon.rooms for actor in room.stage.actors]
    )
    dbg_game.create_stage_entities([room.stage for room in dungeon.rooms])

    # 7. 标记实体已创建
    dungeon.setup_entities = True

    logger.info(f"setup_dungeon 完成: {dungeon.name}")
    return True, f"副本实体创建完成: {dungeon.name}"


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

    # 4. 将运行时实体状态同步回序列化字段
    dbg_game.flush_entities()

    logger.debug("[teardown_dungeon] 副本实体清理完成，dungeon 已重置")
