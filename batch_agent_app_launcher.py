from loguru import logger
import os
from typing import Set, List
import json
from models.config_models import GameAgentsConfigModel
import game.rpg_game_config as rpg_game_config
from pathlib import Path
from models.config_models import GlobalConfigModel


####################################################################################################################################
def _get_unique_agentpy_names(game_names: List[str]) -> Set[str]:

    ret_unique_agentpy_names: Set[str] = set()

    for game_name in game_names:

        agents_config_file_path = (
            rpg_game_config.ROOT_GEN_GAMES_DIR / f"{game_name}_agents.json"
        )
        if (
            not agents_config_file_path.exists()
            or not agents_config_file_path.is_file()
        ):
            logger.error(f"File does not exist: {agents_config_file_path}")
            continue

        try:

            content: str = agents_config_file_path.read_text(encoding="utf-8")
            game_agents_config_model: GameAgentsConfigModel = (
                GameAgentsConfigModel.model_validate(json.loads(content))
            )

            for dict1 in game_agents_config_model.actors:
                for key1, value1 in dict1.items():
                    ret_unique_agentpy_names.add(value1)

            for dict2 in game_agents_config_model.stages:
                for key2, value2 in dict2.items():
                    ret_unique_agentpy_names.add(value2)

            for dict3 in game_agents_config_model.world_systems:
                for key3, value3 in dict3.items():
                    ret_unique_agentpy_names.add(value3)

        except Exception as e:
            logger.error(e)
            assert False, e

    return ret_unique_agentpy_names


####################################################################################################################################
def _get_unique_agentpy_file_paths(unique_agentpy_names: Set[str]) -> List[Path]:

    ## 只读这个目录下的agentpy文件
    final_gen_agents_dir = (
        rpg_game_config.ROOT_GEN_AGENTS_DIR
        / rpg_game_config.CHECK_GAME_RESOURCE_VERSION
    )
    if not final_gen_agents_dir.exists():
        assert False, f"final_gen_agents_dir does not exist: {final_gen_agents_dir}"
        return []

    unique_agentpy_file_paths: List[Path] = []
    for agentpy_name in unique_agentpy_names:
        agentpy_file_path = final_gen_agents_dir / agentpy_name
        if not agentpy_file_path.exists() or not agentpy_file_path.is_file():
            assert False, f"File does not exist: {agentpy_file_path}"
            continue

        unique_agentpy_file_paths.append(agentpy_file_path)

    return unique_agentpy_file_paths


####################################################################################################################################
def _run_agents(game_names: List[str]) -> None:

    unique_agentpy_names: Set[str] = _get_unique_agentpy_names(game_names)
    if len(unique_agentpy_names) == 0:
        assert False, "unique_agentpy_names == 0"
        return None

    # 合成所有的agentpy文件的路径
    unique_agentpy_file_paths: List[Path] = _get_unique_agentpy_file_paths(
        unique_agentpy_names
    )
    if len(unique_agentpy_file_paths) == 0:
        assert False, "unique_agentpy_file_paths == 0"
        return None

    # 转化成字符串路径
    termianl_commands: List[str] = []
    for agentpy_file_path in unique_agentpy_file_paths:
        termianl_commands.append(str(agentpy_file_path))

    # 最后执行组成指令
    # logger.debug(f"agentpy_paths: {termianl_commands}")
    terminal_batch_start_command = f"pm2 start {' '.join(termianl_commands)}"
    logger.debug(terminal_batch_start_command)

    # 执行！！！！！！
    os.system("pm2 list")
    os.system("pm2 delete all")
    os.system(terminal_batch_start_command)


####################################################################################################################################
def main() -> None:
    """
    直接根据一个游戏文件，执行文件内的所有agentpy程序。这样可以清晰一些，手动很麻烦。
    尤其是改了生成之后。
    """

    final_game_names: List[str] = []

    # 读config.json
    config_file_config = rpg_game_config.ROOT_GEN_GAMES_DIR / f"config.json"
    assert config_file_config.exists()
    read_config_content = config_file_config.read_text(encoding="utf-8")
    global_config_model = GlobalConfigModel.model_validate_json(read_config_content)

    #
    available_games: List[str] = []
    for game_config in global_config_model.game_configs:
        available_games.append(game_config.game_name)

    #
    while True:

        usr_input = input(
            f"请输入要进入的游戏(必须与自动化创建一致), 可以是{available_games}之一，空输入为全部生成:"
        )
        if usr_input == "":
            final_game_names = available_games.copy()
            break
        elif usr_input in available_games:
            final_game_names.append(usr_input)
            break
        else:
            continue

    if len(final_game_names) == 0:
        logger.error("没有找到游戏")
        return None

    _run_agents(final_game_names)


####################################################################################################################################
if __name__ == "__main__":
    main()
