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
from extended_systems.lang_serve_system import LangServeSystem
from player.player_proxy import PlayerProxy
from models.player_models import PlayerProxyModel
import game.tcg_game_utils

# from extended_systems.tcg_prop_file_manage_system import PropFileManageSystem
from player.player_command2 import PlayerCommand2


###############################################################################################################################################
@dataclass
class OptionParameters:
    user: str
    game: str
    new_game: bool = True


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

    # 创建游戏运行时目录
    users_world_runtime_dir = (
        game.tcg_game_config.GEN_RUNTIME_DIR / user_name / game_name
    )

    # 强制删除一次
    if users_world_runtime_dir.exists():
        if option.new_game:
            shutil.rmtree(users_world_runtime_dir)

    # 创建目录
    users_world_runtime_dir.mkdir(parents=True, exist_ok=True)
    assert users_world_runtime_dir.exists()

    # todo
    game.tcg_game_utils.create_test_world(game_name, "0.0.1")

    # 创建游戏的根文件是否存在。
    world_root_file_path = game.tcg_game_config.GEN_WORLD_DIR / f"{game_name}.json"
    if not world_root_file_path.exists():
        logger.error(
            f"找不到启动游戏世界的文件 = {world_root_file_path}, 没有用编辑器生成"
        )
        return

    # 游戏资源可以被创建，则将game_resource_file_path这个文件拷贝一份到root_runtime_dir下
    shutil.copy(world_root_file_path, users_world_runtime_dir)

    # 创建runtime
    world_runtime = WorldRuntime()
    users_world_runtime_file_path = users_world_runtime_dir / f"runtime.json"
    if not users_world_runtime_file_path.exists():

        # runtime文件不存在，需要做第一次创建
        copy_root_path = users_world_runtime_dir / f"{game_name}.json"
        assert copy_root_path.exists()

        world_root_file_content = copy_root_path.read_text(encoding="utf-8")
        world_root = WorldRoot.model_validate_json(world_root_file_content)

        world_runtime = WorldRuntime(root=world_root)
        users_world_runtime_file_path.write_text(
            world_runtime.model_dump_json(), encoding="utf-8"
        )

    else:

        # runtime文件存在，需要做恢复
        world_runtime_file_content = users_world_runtime_file_path.read_text(
            encoding="utf-8"
        )
        world_runtime = WorldRuntime.model_validate_json(world_runtime_file_content)

    # 先写死。后续需要改成配置文件
    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    lang_serve_system = LangServeSystem(f"{game_name}-langserve_system")
    lang_serve_system.add_remote_runnable(url=server_url)

    # 创建空游戏
    terminal_tcg_game = TerminalTCGGame(
        name=game_name,
        world_runtime=world_runtime,
        world_runtime_path=users_world_runtime_file_path,
        context=TCGGameContext(),
        langserve_system=lang_serve_system,
        # prop_file_system=PropFileManageSystem(),
        chaos_engineering_system=EmptyChaosEngineeringSystem(),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_tcg_game.world_runtime.entities_snapshot) == 0:
        logger.warning(f"游戏中没有实体 = {game_name}, 说明是第一次创建游戏")
        terminal_tcg_game.build_entities().save()
    else:
        logger.warning(
            f"游戏中有实体 = {game_name}，需要通过数据恢复实体，是游戏回复的过程"
        )
        # 测试！回复ecs
        terminal_tcg_game.restore_entities().save()

    # 加入玩家的数据结构
    player_proxy = PlayerProxy(PlayerProxyModel(player_name=user_name))
    terminal_tcg_game.add_player(player_proxy)

    if not terminal_tcg_game.ready():
        logger.error(f"游戏准备失败 = {game_name}")
        exit(1)

    # 核心循环
    while True:

        usr_input = input(f"[{player_proxy.player_name}]:")
        if usr_input == "":
            logger.debug(f"玩家输入为空 = {player_proxy.player_name}，空跑一次")
            await terminal_tcg_game.a_execute()
            continue

        if usr_input == "/quit" or usr_input == "/q":
            logger.info(f"玩家退出游戏 = {player_proxy.player_name}")
            break

        if usr_input == "/tp":
            terminal_tcg_game.teleport_actors_to_stage(
                {terminal_tcg_game.get_player_entity()}, "场景.洞窟"
            )
            continue

        player_proxy.add_player_command(
            PlayerCommand2(user=player_proxy.player_name, command=usr_input)
        )
        await terminal_tcg_game.a_execute()

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
