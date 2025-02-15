from loguru import logger
import datetime
import game.rpg_game_utils
from dataclasses import dataclass
import game.tcg_game_config
import shutil
from game.tcg_game_context import TCGGameContext
from game.terminal_tcg_game import TerminalTCGGame
from models.entity_models import WorldRoot, WorldRuntime


###############################################################################################################################################
@dataclass
class OptionParameters:
    user: str
    game: str


###############################################################################################################################################
async def run_game(option: OptionParameters) -> None:

    # 读取用户输入
    user_name = option.user
    game_name = option.game

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

    # 创建log
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = game.tcg_game_config.LOGS_DIR / user_name / game_name
    logger.add(log_dir / f"{log_start_time}.log", level="DEBUG")
    logger.info(f"准备进入游戏 = {game_name}, {user_name}")

    # todo 测试，临时写一个json文件, 以后会用自动化生成的
    world_root = WorldRoot(name=game_name, version="0.0.1")
    try:
        write_path = game.tcg_game_config.GEN_WORLD_DIR / f"{game_name}.json"
        write_path.write_text(world_root.model_dump_json(), encoding="utf-8")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

    # 读取world_root文件
    world_root_file_path = game.tcg_game_config.GEN_WORLD_DIR / f"{game_name}.json"
    if not world_root_file_path.exists():
        logger.error(
            f"找不到启动游戏世界的文件 = {world_root_file_path}, 没有用编辑器生成"
        )
        return

    # 创建游戏运行时目录
    users_world_runtime_dir = (
        game.tcg_game_config.GEN_RUNTIME_DIR / user_name / game_name
    )

    # todo 强制删除一次
    if users_world_runtime_dir.exists():
        shutil.rmtree(users_world_runtime_dir)

    # 创建目录
    users_world_runtime_dir.mkdir(parents=True, exist_ok=True)
    assert users_world_runtime_dir.exists()

    # 游戏资源可以被创建，则将game_resource_file_path这个文件拷贝一份到root_runtime_dir下
    shutil.copy(world_root_file_path, users_world_runtime_dir)

    # 读取启动游戏的文件
    world_root_file_content = world_root_file_path.read_text(encoding="utf-8")
    world_root = WorldRoot.model_validate_json(world_root_file_content)

    # 创建runtime model chrono_trace_snapshot
    world_runtime = WorldRuntime(root=world_root)
    users_world_runtime_file_path = users_world_runtime_dir / f"runtime.json"
    users_world_runtime_file_path.write_text(
        world_runtime.model_dump_json(), encoding="utf-8"
    )

    # 创建空游戏
    terminal_tcg_game = TerminalTCGGame(game_name, world_runtime, TCGGameContext())
    terminal_tcg_game.context.restore_from_snapshot(
        terminal_tcg_game._world_runtime.entities_snapshot
    )

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

    asyncio.run(run_game(OptionParameters(user="yanghang", game="Game1")))
