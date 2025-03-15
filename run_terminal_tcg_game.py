from loguru import logger
import datetime
import game.rpg_game_utils
from dataclasses import dataclass
import game.tcg_game_config
import shutil
from game.terminal_tcg_game import TerminalTCGGame
from tcg_models.v_0_0_1 import Boot, World
from chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from extended_systems.lang_serve_system import LangServeSystem
from player.player_proxy import PlayerProxy
from rpg_models.player_models import PlayerProxyModel
import game.tcg_game_utils
from player.player_command2 import PlayerCommand2

# from extended_systems.tcg_game_battle_manager import BattleManager


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
    world_boot_file_path = game.tcg_game_config.GEN_WORLD_DIR / f"{game_name}.json"
    if not world_boot_file_path.exists():
        logger.error(
            f"找不到启动游戏世界的文件 = {world_boot_file_path}, 没有用编辑器生成"
        )
        return

    # 游戏资源可以被创建，则将game_resource_file_path这个文件拷贝一份到world_boot_file_path下
    shutil.copy(world_boot_file_path, users_world_runtime_dir)

    # 创建runtime
    world = World()

    #
    users_world_runtime_file_path = users_world_runtime_dir / f"runtime.json"
    if not users_world_runtime_file_path.exists():

        # runtime文件不存在，需要做第一次创建
        copy_boot_path = users_world_runtime_dir / f"{game_name}.json"
        assert copy_boot_path.exists()

        world_boot_file_content = copy_boot_path.read_text(encoding="utf-8")
        world_boot = Boot.model_validate_json(world_boot_file_content)

        world = World(boot=world_boot)
        users_world_runtime_file_path.write_text(
            world.model_dump_json(), encoding="utf-8"
        )

    else:

        # runtime文件存在，需要做恢复
        world_runtime_file_content = users_world_runtime_file_path.read_text(
            encoding="utf-8"
        )
        world = World.model_validate_json(world_runtime_file_content)

    # 先写死。后续需要改成配置文件
    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    lang_serve_system = LangServeSystem(f"{game_name}-langserve_system")
    lang_serve_system.add_remote_runnable(url=server_url)

    # 创建空游戏
    terminal_tcg_game = TerminalTCGGame(
        name=game_name,
        world=world,
        world_path=users_world_runtime_file_path,
        langserve_system=lang_serve_system,
        # battle_manager=BattleManager(users_world_runtime_file_path.parent),
        chaos_engineering_system=EmptyChaosEngineeringSystem(),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_tcg_game.world.entities_snapshot) == 0:
        logger.warning(f"游戏中没有实体 = {game_name}, 说明是第一次创建游戏")
        terminal_tcg_game.build_entities().save()
    else:
        logger.warning(
            f"游戏中有实体 = {game_name}，需要通过数据恢复实体，是游戏回复的过程"
        )
        # 测试！回复ecs
        terminal_tcg_game.restore_entities().save()

    # 加入玩家的数据结构
    terminal_tcg_game.player = PlayerProxy(PlayerProxyModel(name=user_name))

    if option.new_game:
        if not terminal_tcg_game.ready():
            logger.error(f"游戏准备失败 = {game_name}")
            exit(1)

    is_first_execution = False

    # 核心循环
    while True:

        if not is_first_execution:
            is_first_execution = True
            logger.warning(
                f"游戏开始 = {game_name}!!!, 第一次的默认执行!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )
            await terminal_tcg_game.a_execute()
            continue

        usr_input = input(f"[{terminal_tcg_game.player.name}]:")

        if usr_input == "/quit" or usr_input == "/q":
            logger.info(f"玩家 主动 退出游戏 = {terminal_tcg_game.player.name}")
            terminal_tcg_game._will_exit = True
            break

        if usr_input == "/tp1":
            terminal_tcg_game.stage_transition(
                terminal_tcg_game.retrieve_all_hero_entities(),
                "场景.哥布林巢穴",
            )
            continue

        # 以上都拦截不住，就是玩家的输入，输入错了， handle input 相关的system 就不执行，空跑一次。
        terminal_tcg_game.player.add_command2(
            PlayerCommand2(user=terminal_tcg_game.player.name, command=usr_input)
        )

        # 执行
        await terminal_tcg_game.a_execute()

        # 处理退出
        if terminal_tcg_game._will_exit:
            break

    # 退出游戏
    terminal_tcg_game.exit()
    exit(0)


def _test_immutable() -> None:

    from pydantic import BaseModel
    from typing import NamedTuple

    class MutableAttributeModel(BaseModel):
        name: str
        hp: int
        maxhp: int
        action_times: int
        max_action_times: int
        strength: int
        agility: int
        wisdom: int

    class AttributeCompoment2(NamedTuple):
        mutable: MutableAttributeModel

    new_attr_comp = AttributeCompoment2(
        mutable=MutableAttributeModel(
            name="yanghang",
            hp=100,
            maxhp=100,
            action_times=1,
            max_action_times=1,
            strength=1,
            agility=1,
            wisdom=1,
        )
    )

    # print(new_attr_comp)
    import random

    new_attr_comp.mutable.name = "yanghang2"
    new_attr_comp.mutable.hp = random.randint(100, 200)
    new_attr_comp.mutable.maxhp = random.randint(100, 200)
    new_attr_comp.mutable.action_times = random.randint(100, 200)
    new_attr_comp.mutable.max_action_times = random.randint(100, 200)
    new_attr_comp.mutable.strength = random.randint(100, 200)
    new_attr_comp.mutable.agility = random.randint(100, 200)
    new_attr_comp.mutable.wisdom = random.randint(100, 200)

    from typing import Dict, Any

    class TestSnapshot(BaseModel):
        data: Dict[str, Any]

    test_snapshot = TestSnapshot(data=new_attr_comp._asdict())
    dump = test_snapshot.model_dump_json()
    print(dump)

    restore_comp = AttributeCompoment2(**test_snapshot.data)
    assert restore_comp is not None

    assert restore_comp is not new_attr_comp
    assert restore_comp.mutable.name == new_attr_comp.mutable.name
    assert restore_comp.mutable.hp == new_attr_comp.mutable.hp
    assert restore_comp.mutable.maxhp == new_attr_comp.mutable.maxhp
    assert restore_comp.mutable.action_times == new_attr_comp.mutable.action_times
    assert (
        restore_comp.mutable.max_action_times == new_attr_comp.mutable.max_action_times
    )
    assert restore_comp.mutable.strength == new_attr_comp.mutable.strength
    assert restore_comp.mutable.agility == new_attr_comp.mutable.agility
    assert restore_comp.mutable.wisdom == new_attr_comp.mutable.wisdom

    pass


###############################################################################################################################################
if __name__ == "__main__":

    _test_immutable()

    import asyncio

    asyncio.run(run_game(OptionParameters(user="yanghang", game="Game1")))
