from pathlib import Path
# from typing import List
# from loguru import logger
# import datetime
from dataclasses import dataclass
from game.tcg_game_config import GEN_RUNTIME_DIR, GEN_WORLD_DIR
import shutil
# from chat_services.chat_server_config import (
#     StartupConfiguration,
# )


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
@dataclass
class UserSessionOptions:

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
    def gen_world_boot_file(self) -> Path:
        return GEN_WORLD_DIR / f"{self.game}.json"

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
    # 设置logger
    # def setup_logger(self) -> None:
    #     # assert self.user != ""
    #     # assert self.game != ""
    #     # log_dir = LOGS_DIR / self.user / self.game
    #     log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    #     logger.add(LOGS_DIR / f"{log_start_time}.log", level="DEBUG")
    #     # logger.debug(f"准备进入游戏 = {self.game}, 玩家 = {self.user}")


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
@dataclass
class TerminalUserSessionOptions(UserSessionOptions):
    debug_enforce_new_game: bool


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
@dataclass
class WebUserSessionOptions(UserSessionOptions):
    pass


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
@dataclass
class ChatSystemOptions:
    user: str
    game: str
    server_setup_config: str

    # @property
    # def localhost_urls(self) -> List[str]:

    #     config_file_path = Path(self.server_setup_config)
    #     assert config_file_path.exists()
    #     if not config_file_path.exists():
    #         logger.error(f"没有找到配置文件: {config_file_path}")
    #         return []

    #     try:

    #         ret: List[str] = []

    #         config_file_content = config_file_path.read_text(encoding="utf-8")
    #         agent_startup_config = StartupConfiguration.model_validate_json(
    #             config_file_content
    #         )

    #         for config in agent_startup_config.service_configurations:
    #             ret.append(f"http://localhost:{config.port}{config.api}")

    #         return ret

    #     except Exception as e:
    #         logger.error(f"Exception: {e}")

    #     return []


###############################################################################################################################################
