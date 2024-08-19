from loguru import logger
import datetime
from pathlib import Path
import os
from typing import List, Dict, Any
import json


def main() -> None:
    """
    直接根据一个游戏文件，执行文件内的所有agentpy程序。这样可以清晰一些，手动很麻烦。
    尤其是改了生成之后。
    """

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    game_name = input("请输入要进入的游戏名称(必须与自动化创建的名字一致):")
    if game_name == "":
        game_name = "World2"

    directory = Path("game_sample/gen_runtimes")
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
        data: Dict[str, List[Dict[str, Any]]] = json.loads(content)

        agentpy_list: List[str] = []
        for key1, value1 in data.items():
            for dict1 in value1:
                for key2, value2 in dict1.items():
                    agentpy_list.append(value2)

        logger.debug(f"agentpy_list: {agentpy_list}")
        command = f"pm2 start {' '.join(agentpy_list)}"
        logger.debug(command)

        os.system("pm2 list")
        os.system("pm2 delete all")
        os.system(command)

    except Exception as e:
        logger.error(e)


if __name__ == "__main__":
    main()
