from loguru import logger
import datetime
import os
from typing import Set, List
import json
from my_models.models_def import GameAgentsConfigModel
import rpg_game.rpg_game_config as rpg_game_config


####################################################################################################################################
def _run_agents(game_names: List[str]) -> None:

    agentpy_paths: Set[str] = set()

    for game_name in game_names:

        file_name = f"{game_name}_agents.json"
        file_path = rpg_game_config.GEN_GAMES_DIR / file_name
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
            return None

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
def main() -> None:
    """
    直接根据一个游戏文件，执行文件内的所有agentpy程序。这样可以清晰一些，手动很麻烦。
    尤其是改了生成之后。
    """

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    final_game_names: List[str] = []

    while True:

        usr_input = input(
            f"请输入要进入的游戏名称(必须与自动化创建的名字一致), 可以是{rpg_game_config.GAME_NAMES}之一，空输入为全部生成:"
        )
        if usr_input == "":
            final_game_names = rpg_game_config.GAME_NAMES.copy()
            break
        elif usr_input in rpg_game_config.GAME_NAMES:
            final_game_names.append(usr_input)
            break
        else:
            continue

    if len(final_game_names) == 0:
        logger.error("没有找到游戏名称")
        return None

    _run_agents(final_game_names)


####################################################################################################################################
if __name__ == "__main__":
    main()
