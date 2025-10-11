import os
from pathlib import Path
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from loguru import logger
from ai_rpg.chat_services.client import ChatClient
from ai_rpg.settings import (
    initialize_server_settings_instance,
)
from ai_rpg.game.config import setup_logger
from ai_rpg.demo.sd_actors import (
    create_actor_moderator,
)
from ai_rpg.demo.sd_world import create_demo_sd_game_boot
from ai_rpg.game.player_client import PlayerClient
from ai_rpg.game.terminal_sd_game import (
    TerminalSDGame,
    TerminalSDGameSessionContext,
)
from ai_rpg.models import (
    World,
)


###############################################################################################################################################
async def _run_game(
    terminal_game_user_options: TerminalSDGameSessionContext,
) -> None:

    # 新的boot
    world_boot = create_demo_sd_game_boot(terminal_game_user_options.game)

    # 新的世界
    new_world = World(boot=world_boot)

    ### 服务器配置
    server_settings = initialize_server_settings_instance(Path("server_settings.json"))

    # 依赖注入，创建新的游戏
    assert new_world is not None, "World data must exist to create a game"
    terminal_game = TerminalSDGame(
        name=terminal_game_user_options.game,
        player_client=PlayerClient(
            name=terminal_game_user_options.user,
            actor=terminal_game_user_options.actor,
        ),
        world=new_world,
    )

    ChatClient.initialize_url_config(server_settings)

    # 启动游戏的判断，是第一次建立还是恢复？
    assert (
        len(terminal_game.world.entities_serialization) == 0
    ), "World data must be empty to create a new game"
    # if len(terminal_game.world.entities_serialization) == 0:
    logger.info(
        f"游戏中没有实体 = {terminal_game_user_options.game}, 说明是第一次创建游戏"
    )
    # 直接构建ecs
    terminal_game.new_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    player_entity = terminal_game.get_player_entity()
    assert player_entity is not None, "玩家实体必须存在"
    if player_entity is None:
        logger.error(
            f"玩家实体不存在 = {terminal_game_user_options.user}, {terminal_game_user_options.game}, {terminal_game_user_options.actor}"
        )
        exit(1)

    # 必须初始化。
    await terminal_game.initialize()

    # 主循环
    while True:

        await _process_player_input(terminal_game)
        if terminal_game.should_terminate:
            break

    # 保存一下。
    terminal_game.save()

    # 退出游戏
    terminal_game.exit()

    # 退出
    exit(0)


###############################################################################################################################################
async def _process_player_input(terminal_game: TerminalSDGame) -> None:

    player_actor_entity = terminal_game.get_player_entity()
    assert player_actor_entity is not None

    player_stage_entity = terminal_game.safe_get_stage_entity(player_actor_entity)
    assert player_stage_entity is not None

    # 其他状态下的玩家输入！！！！！！
    usr_input = input(
        f"[{terminal_game.player_client.name}/{player_stage_entity.name}/{player_actor_entity.name}]:"
    )
    usr_input = usr_input.strip().lower()

    # 处理输入
    if usr_input == "/q" or usr_input == "/quit":
        # 退出游戏
        logger.debug(
            f"玩家 主动 退出游戏 = {terminal_game.player_client.name}, {player_stage_entity.name}"
        )
        terminal_game.should_terminate = True
        return

    # 公用：检查内网的llm服务的健康状态
    if usr_input == "/hc":
        await ChatClient.health_check()
        return

    if usr_input == "/ad" or usr_input == "/advancing":
        await terminal_game.main_pipeline.process()


###############################################################################################################################################
if __name__ == "__main__":

    import datetime

    setup_logger()

    random_name = f"player-{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}"
    fixed_name = "player-fixed"

    # 做一些设置
    terminal_user_session_options = TerminalSDGameSessionContext(
        user=random_name,
        game="Game2",
        actor=create_actor_moderator().name,
    )

    # 运行游戏
    import asyncio

    asyncio.run(_run_game(terminal_user_session_options))
