from loguru import logger
from multi_agents_game.game.terminal_tcg_game import TerminalTCGGame
from multi_agents_game.game.tcg_game import TCGGameState
from multi_agents_game.models import World, CombatResult
from multi_agents_game.chaos_engineering.empty_engineering_system import (
    EmptyChaosEngineeringSystem,
)
from multi_agents_game.chat_services.chat_system import ChatSystem
from multi_agents_game.player.player_proxy import PlayerProxy
from multi_agents_game.demo import create_demo_dungeon1, create_actor_warrior
from multi_agents_game.tcg_game_systems.combat_monitor_system import CombatMonitorSystem
from multi_agents_game.game.game_options import TerminalGameUserOptions
from multi_agents_game.format_string.terminal_input import (
    parse_speak_command_input,
)
from multi_agents_game.config.game_config import setup_logger, GLOBAL_GAME_NAME
from multi_agents_game.config.server_config import chat_server_localhost_urls
from uuid import uuid4


###############################################################################################################################################
async def run_game(
    terminal_game_user_options: TerminalGameUserOptions,
) -> None:

    # 注意，如果确定player是固定的，但是希望每次玩新游戏，就调用这句。
    # 或者，换成random_name，随机生成一个player名字。
    terminal_game_user_options.delete_world_data()

    # 先检查一下world_data是否存在
    world_exists = terminal_game_user_options.world_data

    #
    if world_exists is None:

        # 获取world_boot_data
        world_boot = terminal_game_user_options.world_boot_data
        assert world_boot is not None, "WorldBootDocument 反序列化失败"

        # 如果world不存在，说明是第一次创建游戏
        world_exists = World(boot=world_boot)

        # 运行时生成地下城系统
        world_exists.dungeon = create_demo_dungeon1()

    else:
        logger.info(
            f"恢复游戏: {terminal_game_user_options.user}, {terminal_game_user_options.game}"
        )

    ### 创建一些子系统。!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    ### 创建一些子系统。!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    # 依赖注入，创建新的游戏
    assert world_exists is not None, "World data must exist to create a game"
    terminal_game = TerminalTCGGame(
        name=terminal_game_user_options.game,
        player=PlayerProxy(
            name=terminal_game_user_options.user,
            actor=terminal_game_user_options.actor,
        ),
        world=world_exists,
        chat_system=ChatSystem(
            name=f"{terminal_game_user_options.game}-chatsystem",
            username=terminal_game_user_options.user,
            localhost_urls=chat_server_localhost_urls(),
        ),
        chaos_engineering_system=EmptyChaosEngineeringSystem(),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_game.world.entities_snapshot) == 0:
        logger.warning(
            f"游戏中没有实体 = {terminal_game_user_options.game}, 说明是第一次创建游戏"
        )
        # 直接构建ecs
        terminal_game.new_game().save()

    else:
        logger.warning(
            f"游戏中有实体 = {terminal_game_user_options.game}，需要通过数据恢复实体，是游戏回复的过程"
        )
        # 测试！回复ecs
        terminal_game.load_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    player_entity = terminal_game.get_player_entity()
    assert player_entity is not None
    if player_entity is None:
        logger.error(
            f"玩家实体不存在 = {terminal_game_user_options.user}, {terminal_game_user_options.game}, {terminal_game_user_options.actor}"
        )
        exit(1)

    # 游戏循环。。。。。。
    while True:

        await _process_player_input(terminal_game)
        if terminal_game.will_exit:
            break

    # 会保存一下。
    terminal_game.save()
    # 退出游戏
    terminal_game.exit()
    # 退出
    exit(0)


###############################################################################################################################################
# TODO, 不封装了。散着写。封装意义也不是很大，乱点乱点吧，以后再说。
async def _process_player_input(terminal_game: TerminalTCGGame) -> None:

    player_actor_entity = terminal_game.get_player_entity()
    assert player_actor_entity is not None

    player_stage_entity = terminal_game.safe_get_stage_entity(player_actor_entity)
    assert player_stage_entity is not None

    # 其他状态下的玩家输入！！！！！！
    usr_input = input(
        f"[{terminal_game.player.name}/{player_stage_entity._name}/{player_actor_entity._name}]:"
    )
    usr_input = usr_input.strip().lower()

    # 处理输入
    if usr_input == "/q" or usr_input == "/quit":
        # 退出游戏
        logger.debug(
            f"玩家 主动 退出游戏 = {terminal_game.player.name}, {player_stage_entity._name}"
        )
        terminal_game.will_exit = True
        return

    # 公用的。
    if usr_input == "/vd" or usr_input == "/view-dungeon":
        logger.info(
            f"当前地下城系统 =\n{terminal_game.current_dungeon.model_dump_json(indent=4)}\n"
        )
        return

    # 乱点乱点吧，测试用，不用太纠结。
    if terminal_game.current_game_state == TCGGameState.DUNGEON:

        if usr_input == "/dk" or usr_input == "/dungeon_combat_kick_off":

            if len(terminal_game.current_engagement.combats) == 0:
                logger.error(f"{usr_input} 没有战斗可以进行！！！！")
                return

            if not terminal_game.current_engagement.is_kickoff_phase:
                logger.error(f"{usr_input} 只能在战斗前is_kickoff_phase使用")
                return

            # 执行一次！！！！！
            await _execute_terminal_game(terminal_game, usr_input)

        elif usr_input == "/dcmp" or usr_input == "/dungeon_combat_complete":

            if len(terminal_game.current_engagement.combats) == 0:
                logger.error(f"{usr_input} 没有战斗可以进行！！！！")
                return

            if not terminal_game.current_engagement.is_complete_phase:
                logger.error(f"{usr_input} 只能在战斗后is_complete_phase使用")
                return

            # 执行一次！！！！！
            await _execute_terminal_game(terminal_game, usr_input)

        elif usr_input == "/dc" or usr_input == "/draw-cards":

            if not terminal_game.current_engagement.is_on_going_phase:
                logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
                return

            logger.debug(f"玩家输入 = {usr_input}, 准备抽卡")
            terminal_game.activate_draw_cards_action()
            await _execute_terminal_game(terminal_game, usr_input)

        elif usr_input == "/pc" or usr_input == "/play-card":

            if not terminal_game.current_engagement.is_on_going_phase:
                logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
                return

            logger.debug(f"玩家输入 = {usr_input}, 准备行动......")
            if terminal_game.execute_play_card():
                # 执行一次！！！！！
                await _execute_terminal_game(terminal_game, usr_input)

        elif usr_input == "/m" or usr_input == "/monitor":

            if not terminal_game.current_engagement.is_on_going_phase:
                logger.error(f"{usr_input} 只能在战斗on_going_phase中使用")
                return

            logger.debug(f"玩家输入 = {usr_input}, 准备监控")
            monitor_utils = CombatMonitorSystem(
                terminal_game,
            )
            await monitor_utils.a_execute1()

        elif usr_input == "/rth" or usr_input == "/return-to-home":

            if (
                len(terminal_game.current_engagement.combats) == 0
                or not terminal_game.current_engagement.is_post_wait_phase
            ):
                logger.error(f"{usr_input} 只能在战斗后使用!!!!!")
                return

            logger.debug(f"玩家输入 = {usr_input}, 准备传送回家")
            terminal_game.return_to_home()

        elif usr_input == "/and" or usr_input == "/advance-next-dungeon":

            if terminal_game.current_engagement.is_post_wait_phase:
                if (
                    terminal_game.current_engagement.combat_result
                    == CombatResult.HERO_WIN
                ):

                    next_level = terminal_game.current_dungeon.next_level()
                    if next_level is None:
                        logger.info("没有下一关，你胜利了，应该返回营地！！！！")
                    else:
                        logger.info(
                            f"玩家输入 = {usr_input}, 进入下一关 = {next_level.name}"
                        )
                        terminal_game.advance_next_dungeon()
                elif (
                    terminal_game.current_engagement.combat_result
                    == CombatResult.HERO_LOSE
                ):
                    logger.info("英雄失败，应该返回营地！！！！")
                else:
                    assert False, "不可能出现的情况！"

        else:
            logger.error(
                f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
            )

    elif terminal_game.current_game_state == TCGGameState.HOME:

        if usr_input == "/ad" or usr_input == "/advancing":
            # 执行一次。
            await _execute_terminal_game(terminal_game, usr_input)

        elif usr_input == "/ld" or usr_input == "/launch-dungeon":

            if len(terminal_game.current_dungeon.levels) == 0:
                logger.error(
                    f"全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！"
                )
                return

            logger.debug(f"玩家输入 = {usr_input}, 准备传送地下城")
            if not terminal_game.launch_dungeon():
                assert False, "传送地下城失败！"

        elif "/speak" in usr_input or "/ss" in usr_input:

            # 分析输入
            speak_command = parse_speak_command_input(usr_input)

            # 处理输入
            if terminal_game.activate_speak_action(
                target=speak_command["target"],
                content=speak_command["content"],
            ):

                # player 执行一次, 这次基本是忽略推理标记的，所有NPC不推理。
                await _execute_terminal_game(terminal_game, usr_input)

                # 其他人执行一次。对应的NPC进行推理。
                await _execute_terminal_game(terminal_game, usr_input)
        else:
            logger.error(
                f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
            )
            # return
    else:
        logger.error(
            f"玩家输入 = {usr_input}, 目前不做任何处理，不在处理范围内！！！！！"
        )


###############################################################################################################################################
async def _execute_terminal_game(
    terminal_game: TerminalTCGGame, usr_input: str
) -> None:

    assert terminal_game.player.name != ""
    logger.debug(f"玩家输入: {terminal_game.player.name} = {usr_input}")

    # 执行一次！！！！！
    await terminal_game.a_execute()


###############################################################################################################################################
if __name__ == "__main__":

    # 初始化日志
    setup_logger()

    random_name = f"player-{uuid4()}"
    fixed_name = "player-fixed"

    # 做一些设置
    terminal_user_session_options = TerminalGameUserOptions(
        user=random_name,
        game=GLOBAL_GAME_NAME,
        actor=create_actor_warrior().name,
    )

    # 运行游戏
    import asyncio

    asyncio.run(run_game(terminal_user_session_options))
