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
from ai_rpg.game.player_client import PlayerClient
from ai_rpg.game.tcg_game import (
    TCGGame,
)
from ai_rpg.models import (
    World,
)
from ai_rpg.demo.werewolf_game_world import (
    create_demo_sd_game_boot,
)

from ai_rpg.entitas import Matcher
from ai_rpg.models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    NightKillFlagComponent,
    DayDiscussionFlagComponent,
)


###############################################################################################################################################
def _is_day_discussion_complete(tcg_game: TCGGame) -> bool:
    players1 = tcg_game.get_group(
        Matcher(
            all_of=[DayDiscussionFlagComponent],
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
                # DayDiscussionFlagComponent,
            ],
        )
    ).entities.copy()

    players2 = tcg_game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
        )
    ).entities.copy()

    return len(players1) >= len(players2)


###############################################################################################################################################
def _announce_night_phase(tcg_game: TCGGame) -> None:

    all_players = tcg_game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
        )
    ).entities.copy()

    # 判断夜晚的逻辑, 0 游戏开始，1 第一夜，2 第一白天，3 第二夜，4 第二白天
    assert tcg_game._time_marker % 2 == 1, "当前时间标记不是夜晚"
    night_value = (tcg_game._time_marker + 1) // 2

    for player in all_players:
        tcg_game.append_human_message(
            player, f"# 注意！天黑请闭眼！这是第 {night_value} 个夜晚"
        )


###############################################################################################################################################
def _announce_day_phase(tcg_game: TCGGame) -> None:

    all_players = tcg_game.get_group(
        Matcher(
            any_of=[
                WerewolfComponent,
                SeerComponent,
                WitchComponent,
                VillagerComponent,
            ],
        )
    ).entities.copy()

    # 判断白天的逻辑, 0 游戏开始，1 第一夜，2 第一白天，3 第二夜，4 第二白天
    assert (
        tcg_game._time_marker % 2 == 0 and tcg_game._time_marker > 0
    ), "当前时间标记不是白天"
    day_value = tcg_game._time_marker // 2

    for player in all_players:
        tcg_game.append_human_message(
            player, f"# 注意！天亮请睁眼！这是第 {day_value} 个白天"
        )

    killed_players = tcg_game.get_group(
        Matcher(
            all_of=[NightKillFlagComponent],
        )
    ).entities.copy()

    # 组织提示词，提示哪些玩家被杀害，以及时间
    if killed_players:
        killed_players_info = ", ".join(
            f"{player.name}(被杀害)" for player in killed_players
        )
        logger.info(f"在夜晚，以下玩家被杀害: {killed_players_info}")
        for player in all_players:
            tcg_game.append_human_message(
                player, f"# 昨晚被杀害的玩家有: {killed_players_info}"
            )

    else:
        logger.info("在夜晚，没有玩家被杀害")
        for player in all_players:
            tcg_game.append_human_message(player, f"# 昨晚没有玩家被杀害，平安夜")


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
    terminal_game = TCGGame(
        name=game,
        player_client=PlayerClient(
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

    # 会保存一下。
    terminal_game.save()

    # 退出游戏
    terminal_game.exit()

    # 退出
    exit(0)


###############################################################################################################################################
async def _process_player_input(terminal_game: TCGGame) -> None:

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

    if usr_input == "/k" or usr_input == "/kickoff":

        if terminal_game._time_marker == 0:
            # 游戏开始
            await terminal_game.werewolf_game_kickoff_pipeline.process()
            assert terminal_game._time_marker == 0, "时间标记应该是0"

        else:
            logger.warning(
                f"当前时间标记不是0，是{terminal_game._time_marker}，不能执行 /kickoff 命令"
            )

        # 返回！
        return

    if usr_input == "/n" or usr_input == "/night":

        # 第一夜的特殊处理
        if terminal_game._time_marker == 0:
            # 第一夜！赋值称为1
            terminal_game._time_marker = 1
            # 通知黑天！
            _announce_night_phase(terminal_game)

        # 运行游戏逻辑
        if terminal_game._time_marker > 0 and terminal_game._time_marker % 2 == 1:
            await terminal_game.werewolf_game_night_pipeline.process()
            terminal_game._time_marker += 1

            _announce_day_phase(terminal_game)
        else:
            logger.warning(
                f"当前不是夜晚{terminal_game._time_marker}，不能执行 /night 命令"
            )

        # 返回！
        return

    if usr_input == "/d" or usr_input == "/day":
        # 运行游戏逻辑
        if terminal_game._time_marker > 0 and terminal_game._time_marker % 2 == 0:
            await terminal_game.werewolf_game_day_pipeline.process()
            # terminal_game._time_marker += 1
            if _is_day_discussion_complete(terminal_game):
                logger.warning(
                    "白天讨论环节完成，需要进入投票阶段！！！！！！！！！！！！"
                )

        else:
            logger.warning(
                f"当前不是白天{terminal_game._time_marker}，不能执行 /day 命令"
            )

        # 返回！
        return


###############################################################################################################################################
if __name__ == "__main__":

    # 初始化日志
    setup_logger()
    import datetime

    random_name = f"player-{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}"
    # fixed_name = "player-fixed"

    # 做一些设置
    user = random_name
    game = GLOBAL_SD_GAME_NAME
    actor = "角色.主持人"  # 写死先！

    # 运行游戏
    import asyncio

    asyncio.run(_run_game(user, game, actor))
