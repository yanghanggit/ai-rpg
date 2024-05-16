from loguru import logger
import datetime
from auxiliary.player_proxy import create_player_proxy, get_player_proxy, TEST_PLAYER_NAME
from auxiliary.player_input_command import (PlayerCommandLogin)
from main_utils import create_rpg_game_then_build


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
def main() -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    worldname = "World2"#input("请输入要进入的世界名称(必须与自动化创建的名字一致):")
    rpggame = create_rpg_game_then_build(worldname)
    if rpggame is None:
        logger.error("create_rpg_game 失败。")
        return

    #测试的代码，上来就控制一个NPC目标，先写死
    create_player_proxy(TEST_PLAYER_NAME)
    playerproxy = get_player_proxy(TEST_PLAYER_NAME)
    assert playerproxy is not None
    playerstartcmd = PlayerCommandLogin("/player-login", rpggame, playerproxy, "无名的复活者")
    playerstartcmd.execute()

    #
    while True:
        if rpggame.exited:
            break
        rpggame.execute()
    #
    rpggame.exit()

if __name__ == "__main__":
    main()