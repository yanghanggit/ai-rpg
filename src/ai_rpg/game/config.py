import datetime
import sys
from pathlib import Path
from typing import Final
from loguru import logger

###########################################################################################################################################
# 生成log的目录
LOGS_DIR: Path = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
assert LOGS_DIR.exists(), f"找不到目录: {LOGS_DIR}"


###########################################################################################################################################
# 游戏世界数据目录
WORLD_BOOT_DIR: Path = Path("world_boots")
WORLD_BOOT_DIR.mkdir(parents=True, exist_ok=True)
assert WORLD_BOOT_DIR.exists(), f"找不到目录: {WORLD_BOOT_DIR}"

###########################################################################################################################################
# 运行时游戏世界数据目录
WORLD_RUNTIME_DIR: Path = Path("world_runtime")
WORLD_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
assert WORLD_RUNTIME_DIR.exists(), f"找不到目录: {WORLD_RUNTIME_DIR}"

###########################################################################################################################################
# 日志配置
LOG_LEVEL: Final[str] = "DEBUG"  # 可以改为 "DEBUG" 来显示详细日志

###########################################################################################################################################
# 全局游戏名称:TCG游戏
GLOBAL_TCG_GAME_NAME: Final[str] = "Game1"

# 全局游戏名称:社交推理游戏-测试的狼人杀
GLOBAL_SD_GAME_NAME: Final[str] = "Game2"


###########################################################################################################################################
# 设置logger
def setup_logger() -> None:
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # 移除默认的控制台处理器
    logger.remove()

    # 添加控制台处理器，使用配置的日志级别
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # 添加文件处理器，保存到指定的 LOGS_DIR 目录
    log_file_path = LOGS_DIR / f"{log_start_time}.log"
    logger.add(log_file_path, level=LOG_LEVEL)

    # 输出配置信息
    logger.info(f"日志配置: 级别={LOG_LEVEL}, 文件路径={log_file_path}")


###########################################################################################################################################
