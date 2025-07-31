from pathlib import Path
from typing import Final
from loguru import logger
import datetime

###########################################################################################################################################
# 生成log的目录
LOGS_DIR: Path = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
assert LOGS_DIR.exists(), f"找不到目录: {LOGS_DIR}"

###########################################################################################################################################
# 全局游戏名称
GLOBAL_GAME_NAME: Final[str] = "Game1"


###########################################################################################################################################
# 设置logger
def setup_logger() -> None:
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(LOGS_DIR / f"{log_start_time}.log", level="DEBUG")


###########################################################################################################################################
