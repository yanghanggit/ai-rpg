import datetime
from pathlib import Path
from typing import Final
from loguru import logger

###########################################################################################################################################
# 生成log的目录
LOGS_DIR: Path = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
assert LOGS_DIR.exists(), f"找不到目录: {LOGS_DIR}"

###########################################################################################################################################
# 全局游戏名称:TCG游戏
GLOBAL_TCG_GAME_NAME: Final[str] = "Game1"

# 全局游戏名称:社交推理游戏-测试的狼人杀
GLOBAL_SD_GAME_NAME: Final[str] = "Game2"


###########################################################################################################################################
# 设置logger
def setup_logger() -> None:
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(LOGS_DIR / f"{log_start_time}.log", level="DEBUG")


###########################################################################################################################################
