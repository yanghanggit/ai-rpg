from loguru import logger
import datetime
from pathlib import Path
import os
from typing import List, Set
import json
from rpg_game.rpg_game_config import GEN_GAMES, RPGGameConfig
from my_data.model_def import GameAgentsConfigModel


####################################################################################################################################
def run_agents(games: List[str]) -> None:
    directory = Path(RPGGameConfig.GAME_SAMPLE_RUNTIME_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.exists() or not directory.is_dir():
        logger.error(f"Directory does not exist: {directory}")
        return None

    agentpy_paths: Set[str] = set()

    for game_name in games:

        file_name = f"{game_name}_agents.json"
        file_path = directory / file_name
        if not file_path.exists() or not file_path.is_file():
            logger.error(f"File does not exist: {file_path}")
            continue

        try:

            content: str = file_path.read_text(encoding="utf-8")
            game_agents_config_model: GameAgentsConfigModel = (
                GameAgentsConfigModel.model_validate(json.loads(content))
            )

            for dict1 in game_agents_config_model.actors:
                for key1, value1 in dict1.items():
                    agentpy_paths.add(value1)

            for dict2 in game_agents_config_model.stages:
                for key2, value2 in dict2.items():
                    agentpy_paths.add(value2)

            for dict3 in game_agents_config_model.world_systems:
                for key3, value3 in dict3.items():
                    agentpy_paths.add(value3)

        except Exception as e:
            logger.error(e)

    if len(agentpy_paths) == 0:
        logger.error("No agentpy paths found.")
        return None

    logger.debug(f"agentpy_paths: {agentpy_paths}")
    terminal_start_command = f"pm2 start {' '.join(agentpy_paths)}"
    logger.debug(terminal_start_command)

    os.system("pm2 list")
    os.system("pm2 delete all")
    os.system(terminal_start_command)


####################################################################################################################################


def main(games: List[str]) -> None:
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")
    run_agents(games)


####################################################################################################################################
if __name__ == "__main__":
    main(GEN_GAMES)
