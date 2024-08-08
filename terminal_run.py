from loguru import logger
import datetime
from player.player_proxy import create_player_proxy
from player.player_command import (PlayerLogin)
from rpg_game.create_rpg_game_funcs import load_then_create_rpg_game, test_save, RPGGameType

async def main(player_actor_name: str) -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    game_name = input("请输入要进入的世界名称(必须与自动化创建的名字一致):")
    if game_name == "":
        game_name = "World2"

    rpg_game = load_then_create_rpg_game(game_name, "qwe", RPGGameType.TERMINAL)
    if rpg_game is None:
        logger.error("create_rpg_game 失败。")
        return
    
    player_actor_name = input(f"""请输入要控制的角色名字(默认为'{player_actor_name}',输入回车为默认):""")
    if player_actor_name == "":
        player_actor_name = player_actor_name 

    player_actor = rpg_game._extended_context.get_actor_entity(player_actor_name)
    if player_actor is None:
        logger.error(f"找不到玩家角色，请检查构建数据:{player_actor_name}")
        return

    player_name_as_terminal_name = "北京柏林互动科技有限公司"
    
    logger.info(f"玩家名字（做为terminal name）:{player_name_as_terminal_name}")
    player_proxy = create_player_proxy(player_name_as_terminal_name)
    assert player_proxy is not None
    # 这个必须调用
    rpg_game.add_player(player_name_as_terminal_name)
    #
    player_login_command = PlayerLogin("/terminal_run_login", rpg_game, player_proxy, player_actor_name, False)
    player_login_command.execute()

    # 测试的代码
    #yh_test_save(game_name)

    #核心循环
    while True:
        if rpg_game.exited:
            break
        await rpg_game.async_execute()
    
    # 退出操作
    rpg_game.exit()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main("无名的复活者")) #todo