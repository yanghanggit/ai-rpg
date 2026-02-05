"""游戏配置模块

定义游戏运行所需的全局配置常量和目录路径。

主要配置：
- LOGS_DIR: 日志文件存储目录
- BLUEPRINTS_DIR: 游戏蓝图配置目录
- WORLDS_DIR: 游戏世界运行时数据目录
- LOG_LEVEL: 日志输出级别
- GAME_1: 默认游戏名称
"""

import datetime
import sys
from pathlib import Path
from typing import Final
from loguru import logger

###########################################################################################################################################
# 日志文件目录
LOGS_DIR: Path = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
assert LOGS_DIR.exists(), f"找不到目录: {LOGS_DIR}"


###########################################################################################################################################
# 游戏蓝图配置目录
BLUEPRINTS_DIR: Path = Path(".blueprints")
BLUEPRINTS_DIR.mkdir(parents=True, exist_ok=True)
assert BLUEPRINTS_DIR.exists(), f"找不到目录: {BLUEPRINTS_DIR}"

###########################################################################################################################################
# 游戏世界运行时数据目录
WORLDS_DIR: Path = Path(".worlds")
WORLDS_DIR.mkdir(parents=True, exist_ok=True)
assert WORLDS_DIR.exists(), f"找不到目录: {WORLDS_DIR}"

###########################################################################################################################################
# 日志级别配置
LOG_LEVEL: Final[str] = "DEBUG"

###########################################################################################################################################
# 默认游戏名称
GAME_1: Final[str] = "Game1"


###########################################################################################################################################
def setup_logger(logs_dir: Path = LOGS_DIR, log_level: str = LOG_LEVEL) -> None:
    """配置并初始化日志系统

    设置控制台和文件两个日志输出处理器，日志文件以时间戳命名。

    Args:
        logs_dir: 日志文件存储目录，默认为 LOGS_DIR
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR），默认为 LOG_LEVEL
    """
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # 移除默认处理器
    logger.remove()

    # 添加控制台处理器
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # 添加文件处理器
    log_file_path = logs_dir / f"{log_start_time}.log"
    logger.add(log_file_path, level=log_level)

    logger.info(f"日志配置: 级别={log_level}, 文件路径={log_file_path}")


###########################################################################################################################################
