from loguru import logger
import datetime
from auxiliary.player_proxy import create_player_proxy, get_player_proxy, TEST_TERMINAL_NAME, TEST_SINGLE_PLAYER_NPC_NAME
from auxiliary.player_input_command import (PlayerCommandLogin)
from main_utils import create_rpg_game_then_build


async def main() -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    worldname = "World2"#input("请输入要进入的世界名称(必须与自动化创建的名字一致):")
    rpggame = create_rpg_game_then_build(worldname)
    if rpggame is None:
        logger.error("create_rpg_game 失败。")
        return
    
    ## 临时 强行改成服务器终端模式，只要这个写死为空。后面的逻辑就会跟上。
    rpggame.extendedcontext.user_ip = ""

    ## 第一次空执行，让所有NPC可以做一些初始化的动作。
    #await rpggame.async_execute()

    #测试的代码，上来就控制一个NPC目标，先写死
    create_player_proxy(TEST_TERMINAL_NAME)
    playerproxy = get_player_proxy(TEST_TERMINAL_NAME)
    assert playerproxy is not None
    playerstartcmd = PlayerCommandLogin("/player-login", rpggame, playerproxy, TEST_SINGLE_PLAYER_NPC_NAME)
    playerstartcmd.execute()

    #
    while True:
        if rpggame.exited:
            break
        await rpggame.async_execute()
        #logger.debug("async_execute done.")
    #
    rpggame.exit()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())