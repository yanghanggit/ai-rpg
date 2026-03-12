"""世界持久化模块

提供游戏世界数据的持久化功能，包括蓝图配置、世界运行时数据、玩家会话等的读写操作。

主要功能：
- 加载游戏蓝图配置（get_game_blueprint_data）
- 加载/保存/删除用户世界数据（get_user_world_data, persist_world_data, delete_user_world_data）
"""

import gzip
from pathlib import Path
from loguru import logger
from ..models import World
from .player_session import PlayerSession


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
# def get_game_blueprint_data(blueprints_dir: Path, game: str) -> Optional[Blueprint]:
#     """加载游戏蓝图配置

#     Args:
#         blueprints_dir: 蓝图配置目录
#         game: 游戏名称

#     Returns:
#         Blueprint: 游戏蓝图对象，失败返回 None
#     """

#     read_path = blueprints_dir / f"{game}.json"
#     assert read_path.exists(), f"游戏启动数据文件不存在: {read_path}"
#     if not read_path.exists():
#         return None

#     try:

#         logger.debug(f"📖 从本地文件系统获取演示游戏世界进行验证...")
#         json_data = read_path.read_text(encoding="utf-8")
#         blueprint_data = Blueprint.model_validate_json(json_data)
#         return blueprint_data

#     except Exception as e:
#         logger.error(f"❌ 从本地文件系统获取演示游戏世界失败: {str(e)}")

#     return None


###############################################################################################################################################
# def get_user_world_data(worlds_dir: Path, user: str, game: str) -> Optional[World]:
#     """加载用户游戏世界运行时数据

#     Args:
#         worlds_dir: 运行时数据目录
#         user: 用户名
#         game: 游戏名称

#     Returns:
#         World: 世界运行时对象，失败返回 None
#     """
#     read_path = worlds_dir / user / game / "runtime.json"
#     if not read_path.exists():
#         return None

#     try:

#         logger.debug(f"📖 从本地文件系统获取用户游戏世界数据...")
#         world_json = read_path.read_text(encoding="utf-8")
#         world_data = World.model_validate_json(world_json)
#         return world_data

#     except Exception as e:
#         logger.error(f"❌ 从本地文件系统获取用户游戏世界数据失败: {str(e)}")

#     return None


# ###############################################################################################################################################
# def delete_user_world_data(worlds_dir: Path, user: str, game: str) -> bool:
#     """删除用户游戏世界数据

#     Args:
#         worlds_dir: 运行时数据目录
#         user: 用户名
#         game: 游戏名称

#     Returns:
#         bool: 删除成功返回 True，目录不存在返回 False
#     """
#     write_dir = worlds_dir / user / game
#     if write_dir.exists():
#         shutil.rmtree(write_dir)
#         logger.debug(f"🗑️ 已删除用户游戏世界数据目录: {write_dir}")
#         return True

#     return False


###############################################################################################################################################
def persist_world_data(
    worlds_dir: Path,
    username: str,
    world: World,
    player_session: PlayerSession,
    enable_gzip: bool = True,
) -> bool:
    """持久化游戏世界数据

    Args:
        worlds_dir: 运行时数据目录
        username: 用户名
        world: 世界对象
        player_session: 玩家会话对象
        enable_gzip: 是否保存压缩版本，默认 True

    Returns:
        bool: 保存成功返回 True，失败返回 False
    """
    game = str(world.blueprint.name)
    write_dir = worlds_dir / username / game
    write_dir.mkdir(parents=True, exist_ok=True)
    assert write_dir.exists(), f"找不到目录: {write_dir}"

    try:
        # 序列化世界数据（只调用一次）
        world_json = world.model_dump_json()

        # 保存 runtime.json
        write_path = write_dir / "world.json"
        write_path.write_text(world_json, encoding="utf-8")
        # logger.debug(f"💾 已保存用户游戏世界数据到文件: {write_path}")

        # 保存 player_session.json
        write_player_session_path = write_dir / "player_session.json"
        write_player_session_path.write_text(
            player_session.model_dump_json(), encoding="utf-8"
        )
        # logger.debug(f"💾 已保存用户玩家会话数据到文件: {write_player_session_path}")

        # 如果需要，保存压缩版本
        if enable_gzip:
            gzip_path = write_dir / "world.json.gz"
            with gzip.open(gzip_path, "wt", encoding="utf-8") as gz_file:
                gz_file.write(world_json)
            # logger.debug(f"💾 已保存用户游戏世界数据到压缩文件: {gzip_path}")

        return True

    except Exception as e:
        logger.error(f"❌ 保存用户游戏世界数据失败: {str(e)}")

    return False
