from llm_serves.config import (
    ServiceConfiguration,
    AgentStartupConfiguration,
    GEN_CONFIGS_DIR,
)
from pathlib import Path
from loguru import logger
import os


##################################################################################################################
def _create_agent_startup_config(name: str) -> AgentStartupConfiguration:
    agent_startup_config = AgentStartupConfiguration()
    agent_startup_config.name = name
    agent_startup_config.service_configurations = [
        ServiceConfiguration(port=8100, temperature=0.7, api="/v1/llm_serve/chat/"),
    ]
    return agent_startup_config


##################################################################################################################
def _prepare_service_configuration(file_path: Path) -> None:

    # 生成配置文件, 写死先
    start_configurations = _create_agent_startup_config(file_path.name)

    # 打印配置文件
    for config in start_configurations.service_configurations:

        logger.debug(f"port: {config.port}")
        assert config.port > 0, "port is 0"

        logger.debug(f"temperature: {config.temperature}")
        assert config.temperature > 0, "temperature is 0"

        logger.debug(f"api: {config.api}")
        assert config.api != "", "api is empty"

        logger.debug(f"fast_api_title: {config.fast_api_title}")
        assert config.fast_api_title != "", "fast_api_title is empty"

        logger.debug(f"fast_api_version: {config.fast_api_version}")
        assert config.fast_api_version != "", "fast_api_version is empty"

        logger.debug(f"fast_api_description: {config.fast_api_description}")
        assert config.fast_api_description != "", "fast_api_description is empty"

    # 保存配置文件
    try:
        dump_json = start_configurations.model_dump_json()
        file_path.write_text(dump_json, encoding="utf-8")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


##################################################################################################################
def _execute_service_startup(config_file_path: Path) -> None:

    try:

        config_file_content = config_file_path.read_text(encoding="utf-8")
        agent_startup_config = AgentStartupConfiguration.model_validate_json(
            config_file_content
        )

        if len(agent_startup_config.service_configurations) == 0:
            logger.error("没有找到配置")
            return None

        # 删除所有进程
        os.system("pm2 delete all")

        # 启动所有进程
        for config in agent_startup_config.service_configurations:
            terminal_batch_start_command = f"pm2 start llm_serves/azure_chat_openai_gpt_4o_graph.py -- {config.port} {config.temperature} {config.api} {config.fast_api_title} {config.fast_api_version} {config.fast_api_description}"
            logger.debug(terminal_batch_start_command)
            os.system(terminal_batch_start_command)

    except Exception as e:
        logger.error(f"An error occurred: {e}")


##################################################################################################################
def main() -> None:

    agent_startup_config_file_path: Path = GEN_CONFIGS_DIR / "start_llm_serves.json"
    if agent_startup_config_file_path.exists():
        agent_startup_config_file_path.unlink()

    # 生成配置文件
    _prepare_service_configuration(agent_startup_config_file_path)

    # 启动服务
    assert (
        agent_startup_config_file_path.exists()
    ), f"找不到配置文件: {agent_startup_config_file_path}"
    _execute_service_startup(agent_startup_config_file_path)  # 写死？


##################################################################################################################

if __name__ == "__main__":
    main()

##################################################################################################################
