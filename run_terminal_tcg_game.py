from loguru import logger
import datetime
import game.rpg_game_utils
from dataclasses import dataclass
import game.rpg_game_config
import shutil
from pydantic import BaseModel
from game.tcg_game_context import TCGGameContext
from game.terminal_tcg_game import TerminalTCGGame


@dataclass
class TerminalGameOption:
    user_name: str
    default_game: str


class TCGGameLaunchModel(BaseModel):
    game_name: str = ""
    version: str = ""


class TCGGameRuntimeModel(BaseModel):
    launch_model: TCGGameLaunchModel = TCGGameLaunchModel()


###############################################################################################################################################
async def run_terminal_game(option: TerminalGameOption) -> None:

    # 读取用户输入
    user_name = option.user_name
    game_name = option.default_game

    # 如果没有输入就用默认值
    while user_name == "":
        user_name = input(f"请输入你的名字:")
        if user_name != "":
            break

    # 如果没有输入就用默认值
    while game_name == "":
        game_name = input(f"请输入要进入的世界(必须与自动化创建的一致):")
        if game_name != "":
            break

    logger.info(f"准备进入游戏 = {game_name}, {user_name}")

    # 创建log
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = game.rpg_game_config.LOGS_DIR / option.user_name / game_name
    logger.add(log_dir / f"{log_start_time}.log", level="DEBUG")

    # 测试，临时写一个json文件, 以后会用自动化生成的
    launch_model = TCGGameLaunchModel(game_name=game_name, version="0.0.1")
    try:
        dump_json = launch_model.model_dump_json()
        write_path = game.rpg_game_config.ROOT_GEN_GAMES_DIR / f"{game_name}.json"
        write_path.write_text(dump_json, encoding="utf-8")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

    # 读取启动游戏的文件
    launch_file_path = game.rpg_game_config.ROOT_GEN_GAMES_DIR / f"{game_name}.json"
    if not launch_file_path.exists():
        logger.error(f"找不到启动游戏世界的文件 = {launch_file_path}, 没有生成")
        return

    # 创建游戏运行时目录，每一次运行都会删除
    game_runtime_dir = (
        game.rpg_game_config.GAMES_RUNTIME_DIR / option.user_name / game_name
    )

    # todo 强制删除一次
    if game_runtime_dir.exists():
        shutil.rmtree(game_runtime_dir)

    game_runtime_dir.mkdir(parents=True, exist_ok=True)
    assert game_runtime_dir.exists()

    # 读取启动游戏的文件
    launch_file_content = launch_file_path.read_text(encoding="utf-8")
    launch_model = TCGGameLaunchModel.model_validate_json(launch_file_content)

    # 创建runtime model
    runtime_model = TCGGameRuntimeModel(launch_model=launch_model)
    runtime_file_path = game_runtime_dir / f"game_runtime.json"
    runtime_file_path.write_text(runtime_model.model_dump_json(), encoding="utf-8")

    # 创建空游戏
    terminal_tcg_game = TerminalTCGGame(game_name, TCGGameContext())

    # 核心循环
    while True:

        usr_input = input(f"[{user_name}]:")
        if usr_input == "":
            continue

        if usr_input == "/quit" or usr_input == "/q":
            logger.info(f"玩家退出游戏 = {user_name}")
            break

        if usr_input == "/load" or usr_input == "/l":
            logger.info(f"玩家加载游戏 = {user_name}, {game_name}")
            continue

        if usr_input == "/execute" or usr_input == "/ex":
            await terminal_tcg_game.a_execute()
            continue

        # 处理退出
        if terminal_tcg_game._will_exit:
            break

    # 退出游戏
    terminal_tcg_game.exit()
    exit(0)


###############################################################################################################################################
if __name__ == "__main__":
    import asyncio

    asyncio.run(
        run_terminal_game(
            TerminalGameOption(user_name="yanghang", default_game="Game1")
        )
    )
