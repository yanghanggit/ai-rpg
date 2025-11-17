import shutil
from pathlib import Path
from typing import Optional
from loguru import logger
from ..models.world import Boot, World
from .player_session import PlayerSession
from ..game.config import WORLD_BOOT_DIR


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
def get_game_boot_data(game: str) -> Optional[Boot]:
    """
    全局方法：从 MongoDB 获取指定游戏的启动世界数据

    Args:
        game: 游戏名称

    Returns:
        Boot 对象或 None
    """

    read_path = WORLD_BOOT_DIR / f"{game}.json"
    assert read_path.exists(), f"游戏启动数据文件不存在: {read_path}"
    if not read_path.exists():
        return None

    try:

        logger.debug(f"📖 从本地文件系统获取演示游戏世界进行验证...")
        boot_json = read_path.read_text(encoding="utf-8")
        boot_data = Boot.model_validate_json(boot_json)
        return boot_data

    except Exception as e:
        logger.error(f"❌ 从本地文件系统获取演示游戏世界失败: {str(e)}")

    return None

    # logger.debug(f"📖 从 MongoDB 获取演示游戏世界进行验证...")
    # stored_boot = mongo_find_one(BootDocument.__name__, {"game_name": game})
    # if stored_boot is None:
    #     logger.error("❌ 启动世界的数据存储到 MongoDB 失败!")
    #     return None

    # # 尝试使用便捷方法反序列化为 WorldBootDocument 对象
    # try:

    #     world_boot_doc = BootDocument.from_mongo(stored_boot)
    #     assert world_boot_doc is not None, "WorldBootDocument 反序列化失败"
    #     return world_boot_doc.boot_data

    # except Exception as e:
    #     logger.error(f"❌ 从 MongoDB 获取演示游戏世界失败: {str(e)}")

    # return None


###############################################################################################################################################
def get_user_world_data(user: str, game: str) -> Optional[World]:
    # """
    # 全局方法：从 MongoDB 获取指定用户和游戏的世界数据

    # Args:
    #     user: 用户名
    #     game: 游戏名称

    # Returns:
    #     World 对象或 None
    # """
    # logger.debug(f"📖 从 MongoDB 获取游戏世界进行验证...")
    # stored_world = mongo_find_one(
    #     # DEFAULT_MONGODB_CONFIG.worlds_collection,
    #     WorldDocument.__name__,
    #     {"username": user, "game_name": game},
    # )
    # if stored_world is None:
    #     logger.warning(f"没有找到游戏世界数据 = {user}:{game}")
    #     return None

    # # 尝试使用便捷方法反序列化为 World 对象
    # try:

    #     world_doc = WorldDocument.from_mongo(stored_world)
    #     assert world_doc is not None, "WorldDocument 反序列化失败"
    #     return world_doc.world_data

    # except Exception as e:
    #     logger.error(f"❌ 从 MongoDB 获取游戏世界失败: {str(e)}")

    return None


###############################################################################################################################################
def delete_user_world_data(user: str) -> None:
    """
    全局方法：删除指定用户的游戏世界数据

    Args:
        user: 用户名
    """
    pass
    # logger.warning(f"🗑️ 删除用户 {user} 的游戏世界数据...")

    # try:
    #     # 删除 MongoDB 中的世界数据
    #     result = mongo_delete_one(WorldDocument.__name__, {"username": user})
    #     if not result:
    #         logger.warning(f"❌ 用户 {user} 的游戏世界数据删除失败或不存在。")

    # except Exception as e:
    #     logger.error(f"❌ 删除用户 {user} 的游戏世界数据失败: {str(e)}")


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
def persist_world_data(username: str, world: World) -> None:
    # """将游戏世界持久化到 MongoDB"""
    pass
    # logger.debug("📝 创建演示游戏世界并存储到 MongoDB...")

    # version = "0.0.1"
    # collection_name = WorldDocument.__name__  # 使用类名作为集合名称

    # try:
    #     # 创建 WorldDocument
    #     world_document = WorldDocument.create_from_world(
    #         username=username, world=world, version="0.0.1"
    #     )

    #     # 保存 WorldDocument 到 MongoDB
    #     # logger.debug(f"📝 存储演示游戏世界到 MongoDB 集合: {collection_name}")
    #     inserted_id = mongo_upsert_one(collection_name, world_document.to_dict())

    #     if inserted_id:
    #         # logger.debug("✅ 演示游戏世界已存储到 MongoDB!")

    #         # 验证已保存的 WorldDocument
    #         # logger.debug("📖 从 MongoDB 获取演示游戏世界进行验证...")

    #         saved_world_data = mongo_find_one(
    #             collection_name,
    #             {
    #                 "username": username,
    #                 "game_name": world.boot.name,
    #             },
    #         )

    #         if not saved_world_data:
    #             logger.error("❌ 从 MongoDB 获取演示游戏世界失败!")
    #         else:
    #             try:
    #                 # 使用便捷方法反序列化为 WorldDocument 对象
    #                 # _world_document = WorldDocument.from_mongodb(retrieved_world_data)
    #                 # logger.success(
    #                 #     f"✅ 演示游戏世界已从 MongoDB 成功获取! = {_world_document.model_dump_json()}"
    #                 # )
    #                 pass
    #             except Exception as validation_error:
    #                 logger.error(f"❌ WorldDocument 反序列化失败: {validation_error}")
    #     else:
    #         logger.error("❌ 演示游戏世界存储到 MongoDB 失败!")

    # except Exception as e:
    #     logger.error(f"❌ 演示游戏世界 MongoDB 操作失败: {e}")
    #     raise


###############################################################################################################################################
def debug_verbose_world_data(
    verbose_dir: Path, world: World, player_session: PlayerSession
) -> None:
    """调试方法，保存游戏状态到文件"""
    verbose_boot_data(verbose_dir, world)
    verbose_world_data(verbose_dir, world)
    verbose_entities_serialization(verbose_dir, world)
    verbose_chat_history(verbose_dir, world)
    verbose_player_session(verbose_dir, player_session)
    verbose_dungeon_system(verbose_dir, world)
    # logger.debug(f"Verbose debug info saved to: {verbose_dir}")


###############################################################################################################################################
def verbose_chat_history(verbose_dir: Path, world: World) -> None:
    """保存聊天历史到文件"""
    chat_history_dir = verbose_dir / "chat_history"
    chat_history_dir.mkdir(parents=True, exist_ok=True)

    for agent_name, agent_memory in world.agents_chat_history.items():
        chat_history_path = chat_history_dir / f"{agent_name}.json"
        chat_history_path.write_text(agent_memory.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
def verbose_boot_data(verbose_dir: Path, world: World) -> None:
    """保存启动数据到文件"""
    boot_data_dir = verbose_dir / "boot_data"
    boot_data_dir.mkdir(parents=True, exist_ok=True)

    boot_file_path = boot_data_dir / f"{world.boot.name}.json"
    if boot_file_path.exists():
        return  # 如果文件已存在，则不覆盖

    # 保存 Boot 数据到文件
    boot_file_path.write_text(world.boot.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
def verbose_world_data(verbose_dir: Path, world: World) -> None:
    """保存世界数据到文件"""
    world_data_dir = verbose_dir / "world_data"
    world_data_dir.mkdir(parents=True, exist_ok=True)
    world_file_path = world_data_dir / f"{world.boot.name}.json"
    world_file_path.write_text(
        world.model_dump_json(), encoding="utf-8"
    )  # 保存 World 数据到文件，覆盖


###############################################################################################################################################
def verbose_player_session(verbose_dir: Path, player_session: PlayerSession) -> None:
    """保存玩家会话数据到文件"""
    player_session_dir = verbose_dir / "player_session"
    player_session_dir.mkdir(parents=True, exist_ok=True)

    player_session_file_path = player_session_dir / f"{player_session.name}.json"
    player_session_file_path.write_text(
        player_session.model_dump_json(), encoding="utf-8"
    )


###############################################################################################################################################
def verbose_entities_serialization(verbose_dir: Path, world: World) -> None:
    """保存实体快照到文件"""
    entities_serialization_dir = verbose_dir / "entities_serialization"
    # 强制删除一次
    if entities_serialization_dir.exists():
        shutil.rmtree(entities_serialization_dir)
    # 创建目录
    entities_serialization_dir.mkdir(parents=True, exist_ok=True)
    assert entities_serialization_dir.exists()

    for entity_serialization in world.entities_serialization:
        entity_serialization_path = (
            entities_serialization_dir / f"{entity_serialization.name}.json"
        )
        entity_serialization_path.write_text(
            entity_serialization.model_dump_json(), encoding="utf-8"
        )


###############################################################################################################################################
def verbose_dungeon_system(verbose_dir: Path, world: World) -> None:
    """保存地下城系统数据到文件"""
    if world.dungeon.name == "":
        return

    dungeon_system_dir = verbose_dir / "dungeons"
    dungeon_system_dir.mkdir(parents=True, exist_ok=True)
    dungeon_system_path = dungeon_system_dir / f"{world.dungeon.name}.json"
    dungeon_system_path.write_text(world.dungeon.model_dump_json(), encoding="utf-8")


###############################################################################################################################################
