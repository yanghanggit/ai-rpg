"""游戏配置模块"""

from pathlib import Path

###########################################################################################################################################
# 游戏蓝图配置目录
BLUEPRINTS_DIR: Path = Path(".blueprints")
BLUEPRINTS_DIR.mkdir(parents=True, exist_ok=True)
assert BLUEPRINTS_DIR.exists(), f"找不到目录: {BLUEPRINTS_DIR}"

###########################################################################################################################################
# 副本配置目录
DUNGEONS_DIR: Path = Path(".dungeons")
DUNGEONS_DIR.mkdir(parents=True, exist_ok=True)
assert DUNGEONS_DIR.exists(), f"找不到目录: {DUNGEONS_DIR}"


###########################################################################################################################################
# 游戏世界运行时数据目录
WORLDS_DIR: Path = Path(".worlds")
WORLDS_DIR.mkdir(parents=True, exist_ok=True)
assert WORLDS_DIR.exists(), f"找不到目录: {WORLDS_DIR}"


###########################################################################################################################################
# 开发期 AI 响应磁盘缓存目录（基于 messages+prompt hash，避免重复调用 AI 接口）
DEBUG_CACHE_DIR: Path = Path(".debug_cache")
DEBUG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
assert DEBUG_CACHE_DIR.exists(), f"找不到目录: {DEBUG_CACHE_DIR}"
