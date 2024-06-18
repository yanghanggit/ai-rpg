from loguru import logger
import datetime
from auxiliary.player_proxy import create_player_proxy, get_player_proxy
from auxiliary.player_command import (PlayerLogin)
from main_utils import load_then_create_rpg_game
from dev_config import TEST_TERMINAL_NAME

async def main() -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    worldname = input("请输入要进入的世界名称(必须与自动化创建的名字一致):")
    rpggame = load_then_create_rpg_game(worldname)
    if rpggame is None:
        logger.error("create_rpg_game 失败。")
        return
    
    ## 临时 强行改成服务器终端模式，只要这个写死为空。后面的逻辑就会跟上。
    rpggame.extendedcontext.user_ips = []
    rpggame.user_ips = []

    #测试的代码，上来就控制一个目标，先写死
    TEST_SINGLE_PLAYER_ACTOR_NAME = "无名的复活者"
    create_player_proxy(TEST_TERMINAL_NAME)
    playerproxy = get_player_proxy(TEST_TERMINAL_NAME)
    assert playerproxy is not None
    playerstartcmd = PlayerLogin("/player-login", rpggame, playerproxy, TEST_SINGLE_PLAYER_ACTOR_NAME)
    playerstartcmd.execute()

    # 核心循环
    while True:
        if rpggame.exited:
            break
        await rpggame.async_execute()
    #
    rpggame.exit()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())