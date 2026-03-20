"""游戏配置模块

定义游戏运行所需的全局配置常量和目录路径。

主要配置：
- BLUEPRINTS_DIR: 游戏蓝图配置目录
- WORLDS_DIR: 游戏世界运行时数据目录
- GAME_1: 默认游戏名称
"""

from pathlib import Path
from typing import Final

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
# 开发期 AI 响应磁盘缓存目录（基于 context+prompt hash，避免重复调用 AI 接口）
DEBUG_CACHE_DIR: Path = Path(".debug_cache")
DEBUG_CACHE_DIR.mkdir(parents=True, exist_ok=True)


###########################################################################################################################################
# 默认游戏名称
GAME_1: Final[str] = (
    "Game1"  # unity 客户端目前是一定会链接到这个游戏的，所以这个名字暂时不能改。
)
GAME_2: Final[str] = "Game2"  # 开发测试用的第二个游戏。
