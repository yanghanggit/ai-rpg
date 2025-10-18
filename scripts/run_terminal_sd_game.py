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
from ai_rpg.game.config import GLOBAL_SD_GAME_NAME, setup_logger
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.tcg_game import (
    SDGame,
)
from ai_rpg.demo.werewolf_game_world import (
    create_demo_sd_game_boot,
)

from ai_rpg.models import (
    World,
)
from ai_rpg.game_systems.werewolf_day_vote_system import WerewolfDayVoteSystem
from ai_rpg.game_services.werewolf_game_services import (
    announce_night_phase,
    announce_day_phase,
)


###############################################################################################################################################
async def _run_game(
    user: str,
    game: str,
    actor: str,
) -> None:

    # 创建boot数据
    world_boot = create_demo_sd_game_boot(game)
    assert world_boot is not None, "WorldBoot 创建失败"

    # 创建游戏实例
    terminal_game = SDGame(
        name=game,
        player_session=PlayerSession(
            name=user,
            actor=actor,
        ),
        world=World(boot=world_boot),
    )

    ### 创建服务器相关的连接信息。
    server_settings = initialize_server_settings_instance(Path("server_settings.json"))
    ChatClient.initialize_url_config(server_settings)

    # 启动游戏的判断，是第一次建立还是恢复？
    assert (
        len(terminal_game.world.entities_serialization) == 0
    ), "World data 中已经有实体，说明不是第一次创建游戏"
    terminal_game.new_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    player_entity = terminal_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在"
    if player_entity is None:
        logger.error(f"玩家实体不存在 = {user}, {game}, {actor}")
        exit(1)

    # 初始化!
    await terminal_game.initialize()

    # 游戏循环。。。。。。
    while True:

        # 处理玩家输入
        await _process_player_input(terminal_game)

        # 检查是否需要终止游戏
        if terminal_game.should_terminate:
            break

    logger.warning("！！！！游戏主循环结束====================================")

    # 会保存一下。
    terminal_game.save()

    # 退出游戏
    terminal_game.exit()

    # 退出
    exit(0)


###############################################################################################################################################
async def _process_player_input(terminal_game: SDGame) -> None:

    player_actor_entity = terminal_game.get_player_entity()
    assert player_actor_entity is not None

    player_stage_entity = terminal_game.safe_get_stage_entity(player_actor_entity)
    assert player_stage_entity is not None

    # 其他状态下的玩家输入！！！！！！
    usr_input = input(
        f"[{terminal_game.player_session.name}/{player_stage_entity.name}/{player_actor_entity.name}]:"
    )
    usr_input = usr_input.strip().lower()
    logger.success(f"玩家输入 = {usr_input}")

    # 处理输入
    if usr_input == "/q" or usr_input == "/quit":
        # 退出游戏
        logger.debug(
            f"玩家 主动 退出游戏 = {terminal_game.player_session.name}, {player_stage_entity.name}"
        )
        terminal_game.should_terminate = True
        return

    # 公用：检查内网的llm服务的健康状态
    if usr_input == "/hc":
        await ChatClient.health_check()
        return

    if usr_input == "/k" or usr_input == "/kickoff":

        if terminal_game._werewolf_game_turn_counter == 0:

            logger.info("游戏开始，准备入场记阶段！！！！！！")

            # 初始化！
            await terminal_game.werewolf_game_kickoff_pipeline.process()

        else:
            logger.warning(
                f"当前时间标记不是0，是{terminal_game._werewolf_game_turn_counter}，不能执行 /kickoff 命令"
            )

        # 返回！
        return

    if usr_input == "/t" or usr_input == "/time":

        last = terminal_game._werewolf_game_turn_counter
        terminal_game._werewolf_game_turn_counter += 1
        logger.info(
            f"时间推进了一步，{last} -> {terminal_game._werewolf_game_turn_counter}"
        )

        # 判断是夜晚还是白天
        if terminal_game._werewolf_game_turn_counter % 2 == 1:

            # 进入下一个夜晚
            announce_night_phase(terminal_game)

        else:
            # 进入下一个白天
            announce_day_phase(terminal_game)

        # 返回！
        return

    if usr_input == "/n" or usr_input == "/night":

        # 如果是夜晚
        if terminal_game._werewolf_game_turn_counter % 2 == 1:

            # 运行游戏逻辑
            await terminal_game.werewolf_game_night_pipeline.process()
        else:

            logger.warning(
                f"当前不是夜晚{terminal_game._werewolf_game_turn_counter}，不能执行 /night 命令"
            )

        # 返回！
        return

    if usr_input == "/d" or usr_input == "/day":

        # 如果是白天
        if (
            terminal_game._werewolf_game_turn_counter % 2 == 0
            and terminal_game._werewolf_game_turn_counter > 0
        ):
            # 运行游戏逻辑
            await terminal_game.werewolf_game_day_pipeline.process()

        else:
            logger.warning(
                f"当前不是白天{terminal_game._werewolf_game_turn_counter}，不能执行 /day 命令"
            )

        # 返回！
        return

    if usr_input == "/v" or usr_input == "/vote":

        # 如果是白天
        if (
            terminal_game._werewolf_game_turn_counter % 2 == 0
            and terminal_game._werewolf_game_turn_counter > 0
        ):

            # 判断是否讨论完毕
            if WerewolfDayVoteSystem.is_day_discussion_complete(terminal_game):

                # 如果讨论完毕，则进入投票环节
                await terminal_game.werewolf_game_vote_pipeline.process()

            else:
                logger.warning(
                    "白天讨论环节没有完成，不能进入投票阶段！！！！！！！！！！！！"
                )
        else:
            logger.warning(
                f"当前不是白天{terminal_game._werewolf_game_turn_counter}，不能执行 /vote 命令"
            )

        # 返回！
        return


###############################################################################################################################################
if __name__ == "__main__":

    # 初始化日志
    setup_logger()
    import datetime

    random_name = f"player-{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}"

    # 做一些设置
    user = random_name
    game = GLOBAL_SD_GAME_NAME
    actor = "角色.主持人"  # 写死先！

    # 运行游戏
    import asyncio

    asyncio.run(_run_game(user, game, actor))
