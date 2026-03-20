"""scripts 模块配置

定义运行脚本所需的目录路径常量。
"""

from pathlib import Path

###########################################################################################################################################
# 日志文件目录
LOGS_DIR: Path = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
assert LOGS_DIR.exists(), f"找不到目录: {LOGS_DIR}"
