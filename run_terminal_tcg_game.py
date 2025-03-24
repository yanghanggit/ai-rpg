from pathlib import Path
from loguru import logger
import datetime
from dataclasses import dataclass
import game.tcg_game_config
import shutil
from game.terminal_tcg_game import TerminalTCGGame
from game.tcg_game import TCGGameState
from models.v_0_0_1 import Boot, World
from chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from extended_systems.lang_serve_system import LangServeSystem
from player.player_proxy import PlayerProxy
from game.tcg_game_demo import (
    create_then_write_demo_world,
    actor_warrior_instance,
    stage_heros_camp_instance,
    stage_dungeon_cave_instance,
)
from player.player_command import PlayerCommand
from extended_systems.combat_system import CombatSystem


###############################################################################################################################################
@dataclass
class UserRuntimeOptions:
    user: str
    game: str
    new_game: bool = True
    langserve_url: str = "http://localhost:8100/v1/llm_serve/chat/"

    ###############################################################################################################################################
    # 生成用户的运行时目录
    @property
    def world_runtime_dir(self) -> Path:

        dir = game.tcg_game_config.GEN_RUNTIME_DIR / self.user / self.game
        if not dir.exists():
            dir.mkdir(parents=True, exist_ok=True)

        assert dir.exists()
        assert dir.is_dir()
        return dir

    ###############################################################################################################################################
    # 生成用户的运行时文件
    @property
    def world_runtime_file(self) -> Path:
        return self.world_runtime_dir / f"runtime.json"

    ###############################################################################################################################################
    # 生成用户的运行时文件
    @property
    def gen_world_boot_file(self) -> Path:
        return game.tcg_game_config.GEN_WORLD_DIR / f"{self.game}.json"

    ###############################################################################################################################################
    # 清除用户的运行时目录, 重新生成
    def clear_runtime_dir(self) -> None:
        # 强制删除一次
        if self.world_runtime_dir.exists():
            shutil.rmtree(self.world_runtime_dir)
        # 创建目录
        self.world_runtime_dir.mkdir(parents=True, exist_ok=True)
        assert self.world_runtime_dir.exists()

    ###############################################################################################################################################
    @property
    def log_dir(self) -> Path:
        return game.tcg_game_config.LOGS_DIR / self.user / self.game

    ###############################################################################################################################################
    # 初始化logger
    def init_logger(self) -> "UserRuntimeOptions":
        log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logger.add(self.log_dir / f"{log_start_time}.log", level="DEBUG")
        logger.info(f"准备进入游戏 = {self.game}, {self.user}")
        return self

    ###############################################################################################################################################


###############################################################################################################################################
async def run_game(option: UserRuntimeOptions) -> None:

    # 这里是临时的TODO
    demo_edit_boot = create_then_write_demo_world(
        option.game, "0.0.1", option.gen_world_boot_file
    )
    assert demo_edit_boot is not None
    if demo_edit_boot is None:
        logger.error(f"创建游戏世界失败 = {option.game}")
        return

    # 如果是新游戏，需要将game_resource_file_path这个文件拷贝一份到world_boot_file_path下
    if option.new_game:

        # 清除用户的运行时目录, 重新生成
        option.clear_runtime_dir()

        # 游戏资源可以被创建，则将game_resource_file_path这个文件拷贝一份到world_boot_file_path下
        shutil.copy(option.gen_world_boot_file, option.world_runtime_dir)

    # 创建runtime
    start_world = World()

    #
    if not option.world_runtime_file.exists():
        # 肯定是新游戏
        assert option.new_game
        # 如果runtime文件不存在，说明是第一次启动，直接从gen文件中读取.
        assert option.gen_world_boot_file.exists()
        # 假设有文件，直接读取
        world_boot_file_content = option.gen_world_boot_file.read_text(encoding="utf-8")
        # 重新生成boot
        world_boot = Boot.model_validate_json(world_boot_file_content)
        # 重新生成world
        start_world = World(boot=world_boot)

    else:

        # 如果runtime文件存在，说明是恢复游戏
        assert not option.new_game
        # runtime文件存在，需要做恢复
        world_runtime_file_content = option.world_runtime_file.read_text(
            encoding="utf-8"
        )
        # 重新生成world,直接反序列化。
        start_world = World.model_validate_json(world_runtime_file_content)

    ### 创建一些子系统。
    # langserve先写死。后续需要改成配置文件
    lang_serve_system = LangServeSystem(f"{option.game}-langserve_system")
    lang_serve_system.add_remote_runnable(url=option.langserve_url)

    # 依赖注入，创建新的游戏
    terminal_game = TerminalTCGGame(
        name=option.game,
        world=start_world,
        world_path=option.world_runtime_file,
        langserve_system=lang_serve_system,
        combat_system=CombatSystem(),
        chaos_engineering_system=EmptyChaosEngineeringSystem(),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_game.world.entities_snapshot) == 0:
        assert option.new_game
        logger.warning(f"游戏中没有实体 = {option.game}, 说明是第一次创建游戏")

        # 直接构建ecs
        terminal_game.build_entities().save()
    else:
        assert not option.new_game
        logger.warning(
            f"游戏中有实体 = {option.game}，需要通过数据恢复实体，是游戏回复的过程"
        )

        # 测试！回复ecs
        terminal_game.restore_entities().save()

    # 加入玩家的数据结构
    terminal_game.player = PlayerProxy(name=option.user)

    # 初始化游戏，玩家必须准备好，否则无法开始游戏
    if option.new_game:
        if not terminal_game.confirm_player_actor_control_readiness(
            actor_warrior_instance
        ):
            logger.error(f"游戏准备失败 = {option.game}")
            exit(1)

    # 进入核心循环
    while True:

        # TODO加一个描述。
        game_state_desc = "未知状态"
        if terminal_game.current_game_state == TCGGameState.HOME:
            game_state_desc = f"营地/{stage_heros_camp_instance.name}"
        elif terminal_game.current_game_state == TCGGameState.DUNGEON:
            game_state_desc = f"地下城/{stage_dungeon_cave_instance.name}"

        # 玩家输入
        usr_input = input(f"[{terminal_game.player.name}/{game_state_desc}]:")

        # 处理输入
        if usr_input == "/quit" or usr_input == "/q":
            # 退出游戏
            logger.info(f"玩家 主动 退出游戏 = {terminal_game.player.name}")
            terminal_game._will_exit = True
            break

        elif usr_input == "/d":

            if terminal_game.current_game_state != TCGGameState.DUNGEON:
                logger.error(f"{usr_input} 只能在地下城中使用")
                continue

            # 测试，直接进入战斗
            if not terminal_game.combat_system.has_combat(
                stage_dungeon_cave_instance.name
            ):
                logger.info(f"玩家输入 = {usr_input}, 开始战斗！")
                terminal_game.combat_system.start_new_combat(
                    stage_dungeon_cave_instance.name
                )

            # 执行一次！！！！！
            terminal_game.player.add_command(
                PlayerCommand(user=terminal_game.player.name, command=usr_input)
            )
            await terminal_game.a_execute()

        elif usr_input == "/h":
            if terminal_game.current_game_state != TCGGameState.HOME:
                logger.error(f"{usr_input} 只能在营地中使用")
                continue

            # 执行一次！！！！！
            terminal_game.player.add_command(
                PlayerCommand(user=terminal_game.player.name, command=usr_input)
            )
            await terminal_game.a_execute()

        else:
            logger.error(
                f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
            )

        # 处理退出
        if terminal_game._will_exit:
            break

    # 退出游戏
    logger.error(f"游戏退出 = {terminal_game.player.name}")
    terminal_game.exit()
    exit(0)


###############################################################################################################################################
if __name__ == "__main__":

    import asyncio

    option = UserRuntimeOptions(user="yanghang", game="Game1").init_logger()
    asyncio.run(run_game(option))
