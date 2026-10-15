"""全局路径常量。

项目内所有目录在此统一定义，导入即创建目录（mkdir + assert）。
注意：所有路径均为相对路径，要求从项目根目录运行。
"""

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
# 资源资产目录（raw 资源 + 同名 .meta）
ASSETS_DIR: Path = Path(".assets/image")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
assert ASSETS_DIR.exists(), f"找不到目录: {ASSETS_DIR}"

###########################################################################################################################################
# 日志文件目录
LOGS_DIR: Path = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
assert LOGS_DIR.exists(), f"找不到目录: {LOGS_DIR}"
