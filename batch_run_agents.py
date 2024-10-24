from loguru import logger
import datetime
from pathlib import Path
import os
from typing import Set
import json
from rpg_game.rpg_game_config import RPGGameConfig
from my_data.model_def import GameAgentsConfigModel


####################################################################################################################################
def run_agents(game_name: str) -> None:
    directory = Path(RPGGameConfig.GAME_SAMPLE_RUNTIME_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.exists() or not directory.is_dir():
        logger.error(f"Directory does not exist: {directory}")
        return None

    file_name = f"{game_name}_agents.json"
    file_path = directory / file_name
    if not file_path.exists() or not file_path.is_file():
        logger.error(f"File does not exist: {file_path}")
        return None

    try:

        content: str = file_path.read_text(encoding="utf-8")
        game_agents_config_model: GameAgentsConfigModel = (
            GameAgentsConfigModel.model_validate(json.loads(content))
        )

        agentpy_paths: Set[str] = set()
        for dict1 in game_agents_config_model.actors:
            for key1, value1 in dict1.items():
                agentpy_paths.add(value1)

        for dict2 in game_agents_config_model.stages:
            for key2, value2 in dict2.items():
                agentpy_paths.add(value2)

        for dict3 in game_agents_config_model.world_systems:
            for key3, value3 in dict3.items():
                agentpy_paths.add(value3)

        if len(agentpy_paths) == 0:
            logger.error("No agentpy paths found.")
            return None

        logger.debug(f"agentpy_paths: {agentpy_paths}")
        terminal_start_command = f"pm2 start {' '.join(agentpy_paths)}"
        logger.debug(terminal_start_command)

        os.system("pm2 list")
        os.system("pm2 delete all")
        os.system(terminal_start_command)

    except Exception as e:
        logger.error(e)


####################################################################################################################################


def main(default_game_name: str) -> None:
    """
    直接根据一个游戏文件，执行文件内的所有agentpy程序。这样可以清晰一些，手动很麻烦。
    尤其是改了生成之后。
    """

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    game_name = input("请输入要进入的游戏名称(必须与自动化创建的名字一致):")
    if game_name == "":
        game_name = default_game_name

    run_agents(game_name)


if __name__ == "__main__":
    main("World1")
