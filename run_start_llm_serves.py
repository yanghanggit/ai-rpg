from typing import List
from pydantic import BaseModel
from llm_serves.start_config_model import StartConfigModel
from pathlib import Path
from loguru import logger
import os


##################################################################################################################
class StartConfigListModel(BaseModel):
    name: str = ""
    config_list: List[StartConfigModel] = []


##################################################################################################################
# 根目录
GEN_CONFIGS_DIR: Path = Path("gen_configs")
GEN_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
assert GEN_CONFIGS_DIR.exists(), f"找不到目录: {GEN_CONFIGS_DIR}"

##################################################################################################################
START_LLM_SERVES_DIR: Path = GEN_CONFIGS_DIR / "start_llm_serves"


##################################################################################################################
def _gen_start_config_list(name: str = "") -> StartConfigListModel:
    config_list = StartConfigListModel()
    config_list.name = name
    config_list.config_list = [
        StartConfigModel(port=8100, temperature=0.7, api="/v1/llm_serve/chat/"),
    ]
    return config_list


##################################################################################################################
def _gen_config() -> None:

    # 生成配置文件, 写死先
    start_configurations = _gen_start_config_list(START_LLM_SERVES_DIR.name)

    # 保存配置文件
    try:
        dump_json = start_configurations.model_dump_json()
        START_LLM_SERVES_DIR.write_text(dump_json, encoding="utf-8")
    except Exception as e:
        logger.error(f"An error occurred: {e}")


##################################################################################################################
def _start_llm_serves(path_param: str) -> None:

    try:

        read_path = Path(path_param)

        read_config_content = read_path.read_text(encoding="utf-8")
        validated_config_model = StartConfigListModel.model_validate_json(
            read_config_content
        )

        if len(validated_config_model.config_list) == 0:
            logger.error("没有找到配置")
            return None

        # 删除所有进程
        os.system("pm2 delete all")

        # 启动所有进程
        for config in validated_config_model.config_list:
            terminal_batch_start_command = f"pm2 start llm_serves/azure_chat_openai_gpt_4o_graph.py -- {config.port} {config.temperature} {config.api} {config.fast_api_title} {config.fast_api_version} {config.fast_api_description}"
            logger.debug(terminal_batch_start_command)
            os.system(terminal_batch_start_command)

    except Exception as e:
        logger.error(f"An error occurred: {e}")


##################################################################################################################
def main() -> None:
    # 生成配置文件
    _gen_config()

    # 启动服务
    _start_llm_serves("gen_configs/start_llm_serves")  # 写死？


##################################################################################################################

if __name__ == "__main__":
    main()

##################################################################################################################
