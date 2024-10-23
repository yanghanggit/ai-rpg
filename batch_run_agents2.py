from loguru import logger
import datetime
from pathlib import Path
import os
from typing import List, Dict, Any, Set
import json
from rpg_game.rpg_game_config import GEN_GAMES, RPGGameConfig


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
            data: Dict[str, List[Dict[str, Any]]] = json.loads(content)
            for key1, value1 in data.items():
                for dict1 in value1:
                    for key2, value2 in dict1.items():
                        agentpy_paths.add(value2)

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
