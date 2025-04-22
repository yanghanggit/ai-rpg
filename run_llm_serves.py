from llm_serves.service_config import (
    ServiceConfiguration,
    StartupConfiguration,
    GEN_CONFIGS_DIR,
)
from pathlib import Path
from loguru import logger
import os


##################################################################################################################
def _create_startup_config(name: str) -> StartupConfiguration:
    agent_startup_config = StartupConfiguration()
    agent_startup_config.name = name
    agent_startup_config.service_configurations = [
        ServiceConfiguration(
            port=8100,
            temperature=0.7,
            api="/v1/llm_serve/chat/",
            fast_api_title="title1",
            fast_api_version="0.0.1",
            fast_api_description="description1",
        ),
        ServiceConfiguration(
            port=8101,
            temperature=0.7,
            api="/v1/llm_serve/chat/",
            fast_api_title="title2",
            fast_api_version="0.0.1",
            fast_api_description="description2",
        ),
        ServiceConfiguration(
            port=8102,
            temperature=0.7,
            api="/v1/llm_serve/chat/",
            fast_api_title="title3",
            fast_api_version="0.0.1",
            fast_api_description="description3",
        ),
    ]
    return agent_startup_config


##################################################################################################################
def _prepare_service_configuration(file_path: Path) -> None:

    # 生成配置文件, 写死先
    start_configurations = _create_startup_config(file_path.name)

    # 打印配置文件
    for config in start_configurations.service_configurations:
        assert config.port > 0, "port is 0"
        assert config.temperature > 0, "temperature is 0"
        assert config.api != "", "api is empty"
        assert config.fast_api_title != "", "fast_api_title is empty"
        assert config.fast_api_version != "", "fast_api_version is empty"
        assert config.fast_api_description != "", "fast_api_description is empty"
        logger.debug(f"\n{config.model_dump_json()}\n")

    # 保存配置文件
    try:
        dump_json = start_configurations.model_dump_json()
        file_path.write_text(dump_json, encoding="utf-8")
    except Exception as e:
        logger.error(f"Exception: {e}")


##################################################################################################################
def _execute_service_startup(config_file_path: Path) -> None:

    try:

        config_file_content = config_file_path.read_text(encoding="utf-8")
        agent_startup_config = StartupConfiguration.model_validate_json(
            config_file_content
        )

        if len(agent_startup_config.service_configurations) == 0:
            logger.error("没有找到配置")
            return

        # 删除所有进程
        os.system("pm2 delete all")

        # 用配置文件的路径启动
        terminal_batch_start_command = (
            f"pm2 start llm_serves/batch_start_langserve.py -- {config_file_path}"
        )
        logger.debug(terminal_batch_start_command)
        os.system(terminal_batch_start_command)

    except Exception as e:
        logger.error(f"Exception: {e}")


##################################################################################################################
def main() -> None:

    # 写死生成文件。
    startup_config_file_path: Path = GEN_CONFIGS_DIR / "start_llm_serves.json"
    if startup_config_file_path.exists():
        startup_config_file_path.unlink()

    # 生成配置文件
    _prepare_service_configuration(startup_config_file_path)

    # 启动服务
    assert (
        startup_config_file_path.exists()
    ), f"找不到配置文件: {startup_config_file_path}"
    logger.debug(f"配置文件: {startup_config_file_path}")
    _execute_service_startup(startup_config_file_path)  # 写死？


##################################################################################################################

if __name__ == "__main__":
    main()

##################################################################################################################
