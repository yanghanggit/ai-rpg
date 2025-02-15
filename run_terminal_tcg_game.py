from loguru import logger
import datetime
import game.rpg_game_utils
from dataclasses import dataclass
import game.tcg_game_config
import shutil
from game.tcg_game_context import TCGGameContext
from game.terminal_tcg_game import TerminalTCGGame
from models.tcg_models import WorldRoot, WorldRuntime
from chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from extended_systems.query_component_system import QueryComponentSystem
from agent.lang_serve_system import LangServeSystem
from player.player_proxy import PlayerProxy
from models.player_models import PlayerProxyModel
import game.tcg_game_utils


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

    # todo
    game.tcg_game_utils.create_test_world(game_name, "0.0.1")
 
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
        #pass
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
    terminal_tcg_game = TerminalTCGGame(
        game_name,
        world_runtime,
        TCGGameContext(
            LangServeSystem(f"{game_name}-langserve_system"),
            QueryComponentSystem(),
            EmptyChaosEngineeringSystem(),
        ),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_tcg_game._world_runtime.entities_snapshot) == 0:
        logger.warning(f"游戏中没有实体 = {game_name}, 说明是第一次创建游戏")
        # 测试！创建世界
        terminal_tcg_game.build()

        # 强行写一次，做测试。
        terminal_tcg_game._world_runtime.entities_snapshot = (
            terminal_tcg_game.context.make_snapshot()
        )
        users_world_runtime_file_path.write_text(
            world_runtime.model_dump_json(), encoding="utf-8"
        )

    else:
        logger.warning(
            f"游戏中有实体 = {game_name}，需要通过数据恢复实体，是游戏回复的过程"
        )
        # 测试！回复ecs
        terminal_tcg_game.restore()

    # 加入玩家的数据结构
    player_proxy = PlayerProxy(PlayerProxyModel(player_name=user_name))
    terminal_tcg_game.add_player(player_proxy)

    # 核心循环
    while True:

        usr_input = input(f"[{player_proxy.player_name}]:")
        if usr_input == "":
            continue

        if usr_input == "/quit" or usr_input == "/q":
            logger.info(f"玩家退出游戏 = {player_proxy.player_name}")
            break

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
