from loguru import logger
import datetime
import player.utils
from player.player_command import PlayerLogin
from rpg_game.create_rpg_game_util import create_rpg_game, RPGGameClientType


async def main(input_actor_name_as_default: str, default_game_name: str) -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    game_name = input(
        f"请输入要进入的世界名称(必须与自动化创建的名字一致), 默认为 {default_game_name} :"
    )
    if game_name == "":
        game_name = default_game_name

    rpg_game = create_rpg_game(game_name, "qwe", RPGGameClientType.TERMINAL)
    if rpg_game is None:
        logger.error("create_rpg_game 失败。")
        return

    final_player_actor_name = input(
        f"""请输入要控制的角色名字(默认为'{input_actor_name_as_default}',输入回车为默认):"""
    )
    if final_player_actor_name == "":
        final_player_actor_name = input_actor_name_as_default

    player_actor = rpg_game._entitas_context.get_actor_entity(final_player_actor_name)
    if player_actor is not None:
        player_name_as_terminal_name = "北京柏林互动科技有限公司"

        logger.info(f"玩家名字（做为terminal name）:{player_name_as_terminal_name}")
        player_proxy = player.utils.create_player_proxy(player_name_as_terminal_name)
        assert player_proxy is not None
        # 这个必须调用
        rpg_game.add_player(player_name_as_terminal_name)
        #
        login_command = PlayerLogin(
            "/terminal_run_login",
            rpg_game,
            player_proxy,
            final_player_actor_name,
            False,
        )
        login_command.execute()
    else:
        logger.error(f"找不到玩家角色，请检查构建数据:{final_player_actor_name}")

    # 核心循环
    while True:
        if rpg_game.exited:
            break
        await rpg_game.async_execute()

    # 退出操作
    rpg_game.exit()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main("人物.火十一", "World1"))  # todo
    #asyncio.run(main("人物.魏行", "World2"))  # todo
