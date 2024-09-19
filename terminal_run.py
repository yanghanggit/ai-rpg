from loguru import logger
import datetime
from player.player_proxy import PlayerProxy
import rpg_game.rpg_game_helper
from rpg_game.rpg_game import RPGGame
from typing import Optional
from dataclasses import dataclass


@dataclass
class TerminalRunOption:
    login_player_name: str
    default_game_name: str
    check_game_resource_version: str
    show_client_message_count: int = 20


async def terminal_run(option: TerminalRunOption) -> None:

    # 读取世界资源文件
    game_name = input(
        f"请输入要进入的世界名称(必须与自动化创建的名字一致), 默认为 {option.default_game_name}:"
    )
    if game_name == "":
        game_name = option.default_game_name

    # 创建游戏
    new_game = rpg_game.rpg_game_helper.create_terminal_rpg_game(
        game_name, option.check_game_resource_version
    )
    if new_game is None:
        logger.error(f"create_rpg_game 失败 = {game_name}")
        return

    # 模拟一个客户端
    player_proxy: Optional[PlayerProxy] = None

    # 是否是控制actor游戏
    player_controlled_actor_name = terminal_player_input_select_controlled_actor(
        new_game
    )
    if player_controlled_actor_name != "":
        logger.info(
            f"{option.login_player_name}:{game_name}:{player_controlled_actor_name}"
        )
        player_proxy = PlayerProxy(option.login_player_name)
        new_game.add_player(player_proxy)

        rpg_game.rpg_game_helper.player_join(
            new_game, player_proxy, player_controlled_actor_name
        )
    else:
        logger.info(
            "没有找到可以控制的角色，可能是game resource里没设置Player，此时就是观看。"
        )

    # 核心循环
    while True:

        if new_game._will_exit:
            break

        # 运行一个回合
        await new_game.a_execute()

        # 有客户端才进行控制。
        if player_proxy is not None:

            player_proxy.show_messages(option.show_client_message_count)

            # 如果死了就退出。
            if player_proxy._over:
                new_game._will_exit = True
                continue

            if rpg_game.rpg_game_helper.is_player_turn(new_game, player_proxy):
                await terminal_player_input(new_game, player_proxy)
            else:
                await terminal_player_wait(new_game, player_proxy)

    rpg_game.rpg_game_helper.save_game(new_game)
    new_game.exit()
    new_game = None  # 其实是废话，习惯性写着吧


###############################################################################################################################################
def terminal_player_input_select_controlled_actor(game: RPGGame) -> str:
    all_names = rpg_game.rpg_game_helper.get_player_ctrl_actor_names(game)
    if len(all_names) == 0:
        return ""

    while True:
        for index, actor_name in enumerate(all_names):
            logger.warning(f"{index+1}. {actor_name}")

        input_actor_index = input("请选择要控制的角色(输入序号):")
        if input_actor_index.isdigit():
            actor_index = int(input_actor_index)
            if actor_index > 0 and actor_index <= len(all_names):
                return all_names[actor_index - 1]
        else:
            logger.debug("输入错误，请重新输入。")

    return ""


#######################################################################################################################################
def terminal_player_input_watch(game_name: RPGGame, player_proxy: PlayerProxy) -> None:
    message = rpg_game.rpg_game_helper.gen_player_watch_message(game_name, player_proxy)
    while True:
        logger.info(message)
        input(f"按任意键继续")
        break


###############################################################################################################################################
async def terminal_player_input(game: RPGGame, player_proxy: PlayerProxy) -> None:

    while True:

        usr_input = input(f"[{player_proxy._name}]:")
        if usr_input == "":
            break

        if usr_input == "/quit":
            logger.info(f"玩家退出游戏 = {player_proxy._name}")
            game._will_exit = True
            break

        elif usr_input == "/watch" or usr_input == "/w":
            terminal_player_input_watch(game, player_proxy)

        elif usr_input == "/check" or usr_input == "/c":
            terminal_player_input_check(game, player_proxy)

        else:
            rpg_game.rpg_game_helper.add_player_command(game, player_proxy, usr_input)
            break


#######################################################################################################################################
def terminal_player_input_check(game_name: RPGGame, player_proxy: PlayerProxy) -> None:
    message = rpg_game.rpg_game_helper.gen_player_check_message(game_name, player_proxy)
    while True:
        logger.info(message)
        input(f"按任意键继续")
        break


###############################################################################################################################################
async def terminal_player_wait(game_name: RPGGame, player_proxy: PlayerProxy) -> None:
    while True:
        input(f"terminal_player_wait 。。。。。。。。。。。。")
        break


###############################################################################################################################################


if __name__ == "__main__":
    import asyncio

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    option = TerminalRunOption(
        login_player_name="北京柏林互动科技有限公司",
        default_game_name="World3",
        check_game_resource_version="qwe",
        show_client_message_count=20,
    )
    asyncio.run(terminal_run(option))  # todo
