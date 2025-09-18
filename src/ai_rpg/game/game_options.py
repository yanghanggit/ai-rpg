from dataclasses import dataclass
from typing import Optional

from loguru import logger

from ..mongodb import (
    BootDocument,
    DEFAULT_MONGODB_CONFIG,
    WorldDocument,
    mongodb_delete_one,
    mongodb_find_one,
)
from ..models.world import Boot, World


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
@dataclass
class UserOptions:

    user: str
    game: str
    actor: str

    ###############################################################################################################################################
    @property
    def world_boot_data(self) -> Optional[Boot]:
        logger.debug(f"📖 从 MongoDB 获取演示游戏世界进行验证...")
        stored_boot = mongodb_find_one(
            DEFAULT_MONGODB_CONFIG.worlds_boot_collection, {"game_name": self.game}
        )
        if stored_boot is None:
            logger.error("❌ 启动世界的数据存储到 MongoDB 失败!")
            return None

        # 尝试使用便捷方法反序列化为 WorldBootDocument 对象
        try:

            world_boot_doc = BootDocument.from_mongodb(stored_boot)
            assert world_boot_doc is not None, "WorldBootDocument 反序列化失败"
            return world_boot_doc.boot_data

        except Exception as e:
            logger.error(f"❌ 从 MongoDB 获取演示游戏世界失败: {str(e)}")

        return None

    ###############################################################################################################################################
    @property
    def world_data(self) -> Optional[World]:
        logger.debug(f"📖 从 MongoDB 获取游戏世界进行验证...")
        stored_world = mongodb_find_one(
            DEFAULT_MONGODB_CONFIG.worlds_collection,
            {"username": self.user, "game_name": self.game},
        )
        if stored_world is None:
            logger.warning(f"没有找到游戏世界数据 = {self.user}:{self.game}")
            return None

        # 尝试使用便捷方法反序列化为 World 对象
        try:

            world_doc = WorldDocument.from_mongodb(stored_world)
            assert world_doc is not None, "WorldDocument 反序列化失败"
            return world_doc.world_data

        except Exception as e:
            logger.error(f"❌ 从 MongoDB 获取游戏世界失败: {str(e)}")

        return None

    ###############################################################################################################################################
    def delete_world_data(self) -> None:
        """
        删除用户的游戏世界数据
        """
        logger.warning(f"🗑️ 删除用户 {self.user} 的游戏世界数据...")

        try:
            # 删除 MongoDB 中的世界数据
            result = mongodb_delete_one(
                DEFAULT_MONGODB_CONFIG.worlds_collection, {"username": self.user}
            )
            if not result:
                logger.warning(f"❌ 用户 {self.user} 的游戏世界数据删除失败或不存在。")

        except Exception as e:
            logger.error(f"❌ 删除用户 {self.user} 的游戏世界数据失败: {str(e)}")
