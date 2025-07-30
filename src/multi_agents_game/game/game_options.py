from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from ..config.game_config import GEN_RUNTIME_DIR, GEN_WORLD_DIR
from ..config.db_config import DEFAULT_MONGODB_CONFIG
import shutil
from loguru import logger
from ..db.mongodb_client import (
    mongodb_find_one,
)
from ..db.mongodb_world_boot_document import WorldBootDocument
from ..models.world import Boot


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
@dataclass
class UserOptions:

    user: str
    game: str
    actor: str

    ###############################################################################################################################################
    # 生成用户的运行时目录
    @property
    def world_runtime_dir(self) -> Path:

        dir = GEN_RUNTIME_DIR / self.user / self.game
        if not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)

        assert dir.exists()
        assert dir.is_dir()
        return dir

    ###############################################################################################################################################
    # 生成用户的运行时文件
    @property
    def world_runtime_file(self) -> Path:
        return self.world_runtime_dir / f"runtime.json"

    ###############################################################################################################################################
    # 生成用户的运行时文件
    @property
    def world_runtime_boot_file(self) -> Path:
        return self.world_runtime_dir / f"{self.game}.json"

    ###############################################################################################################################################
    # 生成用户的运行时文件
    @property
    def world_boot_file(self) -> Path:
        return GEN_WORLD_DIR / f"{self.game}.json"

    ###############################################################################################################################################
    @property
    def world_boot_data(self) -> Optional[Boot]:
        logger.info(f"📖 从 MongoDB 获取演示游戏世界进行验证...")
        stored_boot = mongodb_find_one(
            DEFAULT_MONGODB_CONFIG.worlds_boot_collection, {"game_name": self.game}
        )
        if stored_boot is None:
            logger.error("❌ 演示游戏世界存储到 MongoDB 失败!")
            return None

        # 尝试使用便捷方法反序列化为 WorldBootDocument 对象
        try:

            world_boot_doc = WorldBootDocument.from_mongodb(stored_boot)
            assert world_boot_doc is not None, "WorldBootDocument 反序列化失败"
            return world_boot_doc.boot_data

        except Exception as e:
            logger.error(f"❌ 从 MongoDB 获取演示游戏世界失败: {str(e)}")

        return None

    ###############################################################################################################################################
    # 清除用户的运行时目录, 重新生成
    def clear_runtime_dir(self) -> None:
        # 强制删除一次
        if self.world_runtime_dir.exists():
            shutil.rmtree(self.world_runtime_dir)
        # 创建目录
        self.world_runtime_dir.mkdir(parents=True, exist_ok=True)
        assert self.world_runtime_dir.exists()

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
@dataclass
class TerminalGameUserOptions(UserOptions):
    debug_enforce_new_game: bool


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
@dataclass
class WebGameUserOptions(UserOptions):
    pass
