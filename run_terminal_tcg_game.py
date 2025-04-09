from loguru import logger
import shutil
from game.terminal_tcg_game import TerminalTCGGame
from game.tcg_game import TCGGameState
from models_v_0_0_1 import Boot, World, CombatResult, Dungeon
from chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from llm_serves.chat_system import ChatSystem
from player.player_proxy import PlayerProxy
from game.tcg_game_demo import (
    create_then_write_demo_world,
    create_demo_dungeon_system,
)
from tcg_game_systems.draw_cards_system import DrawCardsSystem
from tcg_game_systems.monitor_system import MonitorSystem
from game.user_session_options import UserSessionOptions
from tcg_game_systems.dungeon_combat_round_system import DungeonCombatRoundSystem


###############################################################################################################################################
async def run_game(option: UserSessionOptions) -> None:

    # 这里是临时的TODO
    demo_edit_boot = create_then_write_demo_world(
        option.game, option.gen_world_boot_file
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
        # 运行时生成地下城系统
        start_world.dungeon = create_demo_dungeon_system(name="哥布林与兽人")

    else:

        # 如果runtime文件存在，说明是恢复游戏
        assert not option.new_game
        # runtime文件存在，需要做恢复
        world_runtime_file_content = option.world_runtime_file.read_text(
            encoding="utf-8"
        )
        # 重新生成world,直接反序列化。
        start_world = World.model_validate_json(world_runtime_file_content)

    ### 创建一些子系统。!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    ### 创建一些子系统。!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    # 依赖注入，创建新的游戏
    terminal_game = TerminalTCGGame(
        name=option.game,
        player=PlayerProxy(name=option.user, actor=option.actor),
        world=start_world,
        world_path=option.world_runtime_file,
        chat_system=ChatSystem(
            name=f"{option.game}-langserve_system",
            user_name=option.user,
            localhost_urls=option.langserve_localhost_urls,
        ),
        chaos_engineering_system=EmptyChaosEngineeringSystem(),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_game.world.entities_snapshot) == 0:

        assert option.new_game
        logger.warning(f"游戏中没有实体 = {option.game}, 说明是第一次创建游戏")

        # 直接构建ecs
        terminal_game.new_game().save()

    else:

        assert not option.new_game
        logger.warning(
            f"游戏中有实体 = {option.game}，需要通过数据恢复实体，是游戏回复的过程"
        )

        # 测试！回复ecs
        terminal_game.load_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    player_entity = terminal_game.get_player_entity()
    assert player_entity is not None
    if player_entity is None:
        logger.error(f"玩家实体不存在 = {option.user}, {option.game}, {option.actor}")
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

    # 如果是战斗后等待阶段，这里临时处理下，
    #######################################################################
    #######################################################################
    #######################################################################
    if (
        len(terminal_game.current_engagement.combats) > 0
        and terminal_game.current_engagement.is_post_wait_phase
    ):
        if terminal_game.current_engagement.combat_result == CombatResult.HERO_WIN:

            next_level = terminal_game.current_dungeon.next_level()
            if next_level is None:
                logger.info("没有下一关，你胜利了，应该返回营地！！！！")
            else:
                while True:
                    usr_input = input(
                        f"下一关为：[{next_level.name}]，可以进入。是否进入？(y/n): "
                    )
                    usr_input = usr_input.strip().lower()
                    if usr_input == "y" or usr_input == "yes":
                        break
                    else:
                        logger.error("暂时未实现，只能点击y")
                        continue

                # 进入下一个循环！！！！
                terminal_game.advance_next_dungeon()
                return

        elif terminal_game.current_engagement.combat_result == CombatResult.HERO_LOSE:
            logger.info("英雄失败，应该返回营地！！！！")
        else:
            assert False, "不可能出现的情况！"

    #######################################################################
    #######################################################################
    #######################################################################

    #######################################################################
    #######################################################################
    #######################################################################
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

    # 乱点乱点吧，测试用，不用太纠结。
    elif usr_input == "/dk" or usr_input == "/dungeon_combat_kick_off":

        # 推进一次战斗。
        if terminal_game.current_game_state != TCGGameState.DUNGEON:
            logger.error(f"{usr_input} 只能在地下城中使用")
            return

        if len(terminal_game.current_engagement.combats) == 0:
            logger.error(f"{usr_input} 没有战斗可以进行！！！！")
            return

        if not terminal_game.current_engagement.is_kickoff_phase:
            logger.error(f"{usr_input} 只能在战斗前is_kickoff_phase使用")
            return

        # 执行一次！！！！！
        await _execute_terminal_game(terminal_game, usr_input)

    elif usr_input == "/dc" or usr_input == "/draw-cards":

        # 抽卡
        if terminal_game.current_game_state != TCGGameState.DUNGEON:
            logger.error(f"{usr_input} 只能在地下城中使用")
            return

        if not terminal_game.current_engagement.is_on_going_phase:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备抽卡")
        draw_card_utils = DrawCardsSystem(
            terminal_game,
        )
        await draw_card_utils.a_execute1()

    elif usr_input == "/nr" or usr_input == "/new-round":

        # 抽卡
        if terminal_game.current_game_state != TCGGameState.DUNGEON:
            logger.error(f"{usr_input} 只能在地下城中使用")
            return

        if not terminal_game.current_engagement.is_on_going_phase:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        # logger.debug(f"玩家输入 = {usr_input}, 准备抽卡")
        combat_round_utils = DungeonCombatRoundSystem(
            terminal_game,
            # terminal_game.retrieve_actors_on_stage(player_stage_entity),
        )

        round = combat_round_utils.setup_round()
        assert not round.is_round_complete
        logger.info(f"新的回合开始 = {round.model_dump_json(indent=4)}")

    elif usr_input == "/pc" or usr_input == "/play-card":

        # 抽卡
        if terminal_game.current_game_state != TCGGameState.DUNGEON:
            logger.error(f"{usr_input} 只能在地下城中使用")
            return

        if not terminal_game.current_engagement.is_on_going_phase:
            logger.error(f"{usr_input} 只能在战斗中使用is_on_going_phase")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备行动......")
        if terminal_game.execute_play_card():
            # 执行一次！！！！！
            await _execute_terminal_game(terminal_game, usr_input)

    elif usr_input == "/m" or usr_input == "/monitor":

        # 监控
        if terminal_game.current_game_state != TCGGameState.DUNGEON:
            logger.error(f"{usr_input} 只能在地下城中使用")
            return

        if not terminal_game.current_engagement.is_on_going_phase:
            logger.error(f"{usr_input} 只能在战斗on_going_phase中使用")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备监控")
        monitor_utils = MonitorSystem(
            terminal_game,
            # set({player_stage_entity}),
            # terminal_game.retrieve_actors_on_stage(player_stage_entity),
        )
        await monitor_utils.a_execute1()

    elif usr_input == "/th" or usr_input == "/trans-home":

        # 战斗后回家。
        if terminal_game.current_game_state != TCGGameState.DUNGEON:
            logger.error(f"{usr_input} 只能在地下城中使用")
            return

        if (
            len(terminal_game.current_engagement.combats) == 0
            or not terminal_game.current_engagement.is_post_wait_phase
        ):
            logger.error(f"{usr_input} 只能在战斗后使用!!!!!")
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备传送回家")

        # 回家
        terminal_game.transition_heroes_to_home()

    elif usr_input == "/vd" or usr_input == "/view-dungeon":
        logger.info(
            f"当前地下城系统 =\n{terminal_game.current_dungeon.model_dump_json(indent=4)}\n"
        )

    elif usr_input == "/rh" or usr_input == "/run-home":

        # 推进一次营地的执行。
        if terminal_game.current_game_state != TCGGameState.HOME:
            logger.error(f"{usr_input} 只能在营地中使用")
            return

        # 执行一次！！！！！
        await _execute_terminal_game(terminal_game, usr_input)
        terminal_game.is_game_started = True

    elif usr_input == "/ld" or usr_input == "/launch-dungeon":

        # 传送进地下城战斗。
        if terminal_game.current_game_state != TCGGameState.HOME:
            logger.error(f"{usr_input} 只能在营地中使用")
            return

        if not terminal_game.is_game_started:
            logger.error(f"{usr_input} 至少要执行一次 /rh，才能准备传送战斗！")
            return

        if len(terminal_game.current_dungeon.levels) == 0:
            logger.error(
                f"全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！"
            )
            return

        logger.debug(f"玩家输入 = {usr_input}, 准备传送地下城")
        if not terminal_game.launch_dungeon():
            assert False, "传送地下城失败！"

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

    import asyncio

    # 做一些设置
    option = UserSessionOptions(
        user="yanghang",
        game="Game1",
        new_game=True,
        server_setup_config="gen_configs/start_llm_serves.json",
        langserve_localhost_urls=[],
        actor="角色.战士.卡恩",
    ).setup()

    # 运行游戏
    asyncio.run(run_game(option))
