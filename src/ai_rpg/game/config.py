"""游戏配置模块

定义游戏运行所需的全局配置常量和目录路径。

主要配置：
- LOGS_DIR: 日志文件存储目录
- BLUEPRINTS_DIR: 游戏蓝图配置目录
- WORLDS_DIR: 游戏世界运行时数据目录
- LOG_LEVEL: 日志输出级别
- GAME_1: 默认游戏名称
"""

from pathlib import Path
from typing import Final

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
# 地下城配置目录
DUNGEONS_DIR: Path = Path(".dungeons")
DUNGEONS_DIR.mkdir(parents=True, exist_ok=True)
assert DUNGEONS_DIR.exists(), f"找不到目录: {DUNGEONS_DIR}"

###########################################################################################################################################
# 游戏世界运行时数据目录
WORLDS_DIR: Path = Path(".worlds")
WORLDS_DIR.mkdir(parents=True, exist_ok=True)
assert WORLDS_DIR.exists(), f"找不到目录: {WORLDS_DIR}"


###########################################################################################################################################
# 默认游戏名称
GAME_1: Final[str] = (
    "Game1"  # unity 客户端目前是一定会链接到这个游戏的，所以这个名字暂时不能改。
)
GAME_2: Final[str] = "Game2"  # 开发测试用的第二个游戏。
