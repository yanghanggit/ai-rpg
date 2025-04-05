from pathlib import Path
from typing import List
from loguru import logger
import datetime
from dataclasses import dataclass
import game.tcg_game_config
import shutil
from llm_serves.service_config import (
    StartupConfiguration,
)


###############################################################################################################################################
@dataclass
class UserSessionOptions:

    user: str
    game: str
    new_game: bool
    server_setup_config: str
    langserve_localhost_urls: List[str]

    ###############################################################################################################################################
    # 生成用户的运行时目录
    @property
    def world_runtime_dir(self) -> Path:

        dir = game.tcg_game_config.GEN_RUNTIME_DIR / self.user / self.game
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
    def gen_world_boot_file(self) -> Path:
        return game.tcg_game_config.GEN_WORLD_DIR / f"{self.game}.json"

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
    @property
    def log_dir(self) -> Path:
        return game.tcg_game_config.LOGS_DIR / self.user / self.game

    ###############################################################################################################################################
    def setup(self) -> "UserSessionOptions":
        return self._init_logger()._generate_service_urls()

    ###############################################################################################################################################
    # 初始化logger
    def _init_logger(self) -> "UserSessionOptions":
        log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logger.add(self.log_dir / f"{log_start_time}.log", level="DEBUG")
        logger.debug(f"准备进入游戏 = {self.game}, {self.user}")
        return self

    ###############################################################################################################################################
    # 生成服务URL
    def _generate_service_urls(self) -> "UserSessionOptions":

        config_file_path = Path(self.server_setup_config)
        assert config_file_path.exists()

        try:

            config_file_content = config_file_path.read_text(encoding="utf-8")
            agent_startup_config = StartupConfiguration.model_validate_json(
                config_file_content
            )

            for config in agent_startup_config.service_configurations:
                self.langserve_localhost_urls.append(
                    f"http://localhost:{config.port}{config.api}"
                )

        except Exception as e:
            logger.error(f"Exception: {e}")
            assert False, "没有找到配置!"

        return self

    ###############################################################################################################################################
