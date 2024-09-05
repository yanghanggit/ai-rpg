from loguru import logger
import datetime
from player.player_proxy import PlayerProxy
from rpg_game.create_rpg_game_util import create_rpg_game, RPGGameClientType
from rpg_game.rpg_game import RPGGame
from gameplay_systems.components import PlayerComponent
from player.player_command import (
    PlayerGoTo,
    PlayerBroadcast,
    PlayerSpeak,
    PlayerWhisper,
    PlayerPickUpProp,
    PlayerSteal,
    PlayerGiveProp,
    PlayerBehavior,
    PlayerEquip,
)

LOGIN_PLAYER_NAME = "北京柏林互动科技有限公司"
DEFAULT_GAME_NAME = "World1"
DEFAULT_VERSION = "qwe"


async def main() -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    game_name = input(
        f"请输入要进入的世界名称(必须与自动化创建的名字一致), 默认为 {DEFAULT_GAME_NAME}:"
    )
    if game_name == "":
        game_name = DEFAULT_GAME_NAME

    rpg_game = create_rpg_game(game_name, DEFAULT_VERSION, RPGGameClientType.TERMINAL)
    if rpg_game is None:
        logger.error(f"create_rpg_game 失败 = {game_name}")
        return

    all_player_controlled_actor_names = rpg_game.get_all_player_controlled_actor_names()
    if len(all_player_controlled_actor_names) == 0:
        logger.error("没有找到可以控制的角色。可能全部是AI角色。")
    else:

        player_controlled_actor_name: str = ""

        while True:
            for index, actor_name in enumerate(all_player_controlled_actor_names):
                logger.warning(f"{index+1}. {actor_name}")
            input_actor_index = input("请选择要控制的角色(输入序号):")
            if input_actor_index.isdigit():
                actor_index = int(input_actor_index)
                if actor_index > 0 and actor_index <= len(
                    all_player_controlled_actor_names
                ):
                    player_controlled_actor_name = all_player_controlled_actor_names[
                        actor_index - 1
                    ]
                    break
            logger.debug("输入错误，请重新输入。")

        if player_controlled_actor_name == "":
            logger.error("没有选择角色!!!!!!")
            return

        logger.info(f"{LOGIN_PLAYER_NAME}:{game_name}:{player_controlled_actor_name}")
        player_proxy = PlayerProxy(LOGIN_PLAYER_NAME)
        assert player_proxy is not None
        rpg_game.add_player(player_proxy)

        player_login(rpg_game, player_proxy, player_controlled_actor_name)

    # 核心循环
    while True:

        if rpg_game._will_exit:
            break

        await rpg_game.a_execute()

        if rpg_game.is_player_input_allowed(player_proxy):
            await player_input(rpg_game, player_proxy)
        else:
            await player_wait(rpg_game, player_proxy)

    # 退出操作
    rpg_game.exit()


###############################################################################################################################################
def player_login(
    rpg_game: RPGGame, player_proxy: PlayerProxy, player_controlled_actor_name: str
) -> None:
    logger.debug("player_login")
    actor_entity = rpg_game._entitas_context.get_actor_entity(
        player_controlled_actor_name
    )
    if actor_entity is None or not actor_entity.has(PlayerComponent):
        logger.error(f"没有找到角色 = {player_controlled_actor_name}")
        return

    # 更改算作登陆成功
    actor_entity.replace(PlayerComponent, player_proxy._name)

    player_proxy.add_system_message(rpg_game.about_game)

    # todo 添加登陆新的信息到客户端消息中
    time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    player_proxy.add_system_message(
        f"login: {player_proxy._name}, time = {time}, 控制角色 = {player_controlled_actor_name}"
    )
    kick_off_messages = rpg_game._entitas_context._kick_off_message_system.get_message(
        player_controlled_actor_name
    )
    if len(kick_off_messages) == 0 or len(kick_off_messages) > 1:
        return
    player_proxy.add_login_message(
        player_controlled_actor_name, kick_off_messages[0].content
    )


###############################################################################################################################################


def add_player_command(
    game_name: RPGGame, player_proxy: PlayerProxy, usr_input: str
) -> None:

    if "/goto" in usr_input:
        player_proxy.add_command(PlayerGoTo("/goto", usr_input))

    elif "/broadcast" in usr_input:
        player_proxy.add_command(PlayerBroadcast("/broadcast", usr_input))

    elif "/speak" in usr_input:
        player_proxy.add_command(PlayerSpeak("/speak", usr_input))

    elif "/whisper" in usr_input:
        player_proxy.add_command(PlayerWhisper("/whisper", usr_input))

    elif "/pickup" in usr_input:
        player_proxy.add_command(PlayerPickUpProp("/pickup", usr_input))

    elif "/steal" in usr_input:
        player_proxy.add_command(PlayerSteal("/steal", usr_input))

    elif "/give" in usr_input:
        player_proxy.add_command(PlayerGiveProp("/give", usr_input))

    elif "/behavior" in usr_input:
        player_proxy.add_command(PlayerBehavior("/behavior", usr_input))

    elif "/equip" in usr_input:
        player_proxy.add_command(PlayerEquip("/equip", usr_input))
    else:
        logger.error(f"无法识别的命令 = {usr_input}")


###############################################################################################################################################


async def player_input(game_name: RPGGame, player_proxy: PlayerProxy, show_messages: int = 20) -> None:
    while True:

        player_proxy.show_messages(show_messages)
        usr_input = input(f"[{player_proxy._name}]:")
        if usr_input == "/quit":
            player_proxy.add_system_message("玩家退出游戏")
            game_name._will_exit = True
        elif usr_input != "":
            add_player_command(game_name, player_proxy, usr_input)
        break


###############################################################################################################################################
async def player_wait(game_name: RPGGame, player_proxy: PlayerProxy) -> None:
    while True:
        input(f"player_wait 。。。。。。。。。。。。")
        break


###############################################################################################################################################


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())  # todo
