import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from loguru import logger
from ai_rpg.chat_services.client import ChatClient
from ai_rpg.configuration import (
    server_configuration,
)
from ai_rpg.game.config import GLOBAL_SDG_GAME_NAME, setup_logger
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.sdg_game import SDGGame
from ai_rpg.demo.werewolf_game_world import (
    create_demo_sd_game_boot,
)

from ai_rpg.models import (
    World,
)
from ai_rpg.services.werewolf_game import (
    VictoryCondition,
    announce_night_phase,
    announce_day_phase,
    is_night_phase_completed,
    is_day_phase_completed,
    check_victory_conditions,
    is_day_discussion_complete,
    is_day_vote_complete,
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
    terminal_game = SDGGame(
        name=game,
        player_session=PlayerSession(name=user, actor=actor, game=game),
        world=World(boot=world_boot),
    )

    ### 创建服务器相关的连接信息。
    ChatClient.initialize_url_config(server_configuration)

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
async def _process_player_input(terminal_game: SDGGame) -> None:

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

        if terminal_game._turn_counter == 0 and not terminal_game._started:

            logger.info("游戏开始，准备入场记阶段！！！！！！")

            # 初始化！
            await terminal_game.werewolf_game_kickoff_pipeline.process()

            # 标记游戏已经开始
            terminal_game._started = True

        else:
            logger.error(
                f"当前时间标记不是0，或者游戏已经开始，是{terminal_game._turn_counter}，不能执行 /kickoff 命令"
            )

        # 返回！
        return

    if usr_input == "/t" or usr_input == "/time":

        if not terminal_game._started:
            logger.error("游戏还没有开始，不能执行 /time 命令")
            return

        if terminal_game._turn_counter > 0:
            # 说明不是第一夜或者第一天
            if terminal_game._turn_counter % 2 == 1:
                # 当前是黑夜（奇数），需要检查夜晚阶段是否完成
                if not is_night_phase_completed(terminal_game):
                    logger.error(
                        "当前夜晚阶段还没有完成，不能推进时间，请先完成夜晚阶段的所有操作"
                    )
                    return

            elif terminal_game._turn_counter % 2 == 0:
                # 当前是白天（偶数），需要检查白天阶段是否完成
                if not is_day_phase_completed(terminal_game):
                    logger.error(
                        "当前白天阶段还没有完成，不能推进时间，请先完成白天阶段的所有操作"
                    )
                    return
            else:
                logger.error(
                    f"当前时间标记异常{terminal_game._turn_counter}，不能执行 /time 命令"
                )
                return

        # 推进时间
        last = terminal_game._turn_counter
        terminal_game._turn_counter += 1
        logger.info(f"时间推进了一步，{last} -> {terminal_game._turn_counter}")

        # 判断是夜晚还是白天
        if terminal_game._turn_counter % 2 == 1:

            # 进入下一个夜晚
            announce_night_phase(terminal_game)

            # await terminal_game.werewolf_game_pass_turn_pipeline.process()

        else:

            # 进入下一个白天
            announce_day_phase(terminal_game)

            # await terminal_game.werewolf_game_pass_turn_pipeline.process()

        # 检查是否达成胜利条件，夜晚会产生击杀
        victory_condition = check_victory_conditions(terminal_game)
        if victory_condition != VictoryCondition.NONE:
            logger.warning("游戏结束，触发胜利条件，准备终止游戏...")
            # 终端游戏就终止掉。
            terminal_game.should_terminate = True
            if victory_condition == VictoryCondition.TOWN_VICTORY:
                logger.warning("\n!!!!!!!!!!!!!!!!!村民阵营胜利!!!!!!!!!!!!!!!!!!!\n")
            elif victory_condition == VictoryCondition.WEREWOLVES_VICTORY:
                logger.warning("\n!!!!!!!!!!!!!!!!!狼人阵营胜利!!!!!!!!!!!!!!!!!!!\n")

        # 返回！
        return

    if usr_input == "/n" or usr_input == "/night":

        # 如果是夜晚
        if terminal_game._turn_counter % 2 == 1:

            if is_night_phase_completed(terminal_game):
                logger.error("夜晚阶段已经完成，不能重复执行 /night 命令")
                return

            # 运行游戏逻辑
            await terminal_game.werewolf_game_night_pipeline.process()
        else:

            logger.error(
                f"当前不是夜晚{terminal_game._turn_counter}，不能执行 /night 命令"
            )

        # 返回！
        return

    if usr_input == "/d" or usr_input == "/day":

        # 如果是白天
        if terminal_game._turn_counter % 2 == 0 and terminal_game._turn_counter > 0:

            if is_day_discussion_complete(terminal_game):
                logger.error("白天讨论环节已经完成，不能重复执行 /day 命令")
                return

            # 运行游戏逻辑
            await terminal_game.werewolf_game_day_pipeline.process()

        else:
            logger.error(
                f"当前不是白天{terminal_game._turn_counter}，不能执行 /day 命令"
            )

        # 返回！
        return

    if usr_input == "/v" or usr_input == "/vote":

        # 如果是白天
        if terminal_game._turn_counter % 2 == 0 and terminal_game._turn_counter > 0:

            if not is_day_discussion_complete(terminal_game):
                logger.error("白天讨论环节还没有完成，不能执行 /vote 命令")
                return

            if is_day_vote_complete(terminal_game):
                logger.error("白天投票环节已经完成，不能重复执行 /vote 命令")
                return

            # 如果讨论完毕，则进入投票环节
            await terminal_game.werewolf_game_vote_pipeline.process()

            victory_condition = check_victory_conditions(terminal_game)
            if victory_condition != VictoryCondition.NONE:
                logger.warning("游戏结束，触发胜利条件，准备终止游戏...")
                # 终端游戏就终止掉。
                terminal_game.should_terminate = True
                if victory_condition == VictoryCondition.TOWN_VICTORY:
                    logger.warning(
                        "\n!!!!!!!!!!!!!!!!!村民阵营胜利!!!!!!!!!!!!!!!!!!!\n"
                    )
                elif victory_condition == VictoryCondition.WEREWOLVES_VICTORY:
                    logger.warning(
                        "\n!!!!!!!!!!!!!!!!!狼人阵营胜利!!!!!!!!!!!!!!!!!!!\n"
                    )

        else:
            logger.error(
                f"当前不是白天{terminal_game._turn_counter}，不能执行 /vote 命令"
            )

        # 返回！
        return

    if "/msg" in usr_input or "/messages" in usr_input:

        # 形如 /msg 10，请提取出数字10
        parts = usr_input.split(" ")
        since_seq = 0
        if len(parts) == 2:

            if parts[0] not in ["/msg", "/messages"]:
                logger.error(
                    "命令格式错误，应为 /msg <since_seq> 或 /messages <since_seq>"
                )
                return

            try:
                since_seq = int(parts[1])

                messages = terminal_game.player_session.get_messages_since(since_seq)
                logger.info(
                    f"共计 {len(messages)} 条新消息, 从 sequence_id {since_seq} 开始获取:"
                )
                for msg in messages:
                    logger.info(f"{msg.model_dump_json(indent=2)}")

            except Exception as e:
                logger.error(f"提取 since_seq 失败: {e}")

        return


###############################################################################################################################################
if __name__ == "__main__":

    # 初始化日志
    setup_logger()
    import datetime

    random_name = f"player-{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}"

    # 做一些设置
    user = random_name
    game = GLOBAL_SDG_GAME_NAME
    actor = "角色.主持人"  # 写死先！

    # 运行游戏
    import asyncio

    asyncio.run(_run_game(user, game, actor))
