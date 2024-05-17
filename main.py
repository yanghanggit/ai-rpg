from typing import Optional
from loguru import logger
import datetime
from auxiliary.dialogue_rule import parse_target_and_message
from auxiliary.player_proxy import create_player_proxy, get_player_proxy, TEST_PLAYER_NAME
from auxiliary.gm_input_command import GMCommandSimulateRequest, GMCommandSimulateRequestThenRemoveConversation, GMCommandPlayerCtrlAnyNPC
from auxiliary.player_input_command import (PlayerCommandLogin)
from typing import Optional
from main_utils import user_input_pre_command, create_rpg_game_then_build

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
    # 先直接执行一次
    rpggame.execute()

    while True:
        systeminput = input("[system input]:")
        if "/quit" in systeminput:
            break
        
        elif "/login" in systeminput:
            # 测试的代码，上来就控制一个NPC目标，先写死
            create_player_proxy(TEST_PLAYER_NAME)
            playerproxy = get_player_proxy(TEST_PLAYER_NAME)
            assert playerproxy is not None
            playerstartcmd = PlayerCommandLogin("/player-login", rpggame, playerproxy, "无名的复活者")
            playerstartcmd.execute()
            rpggame.execute() # 测试 直接跑一次

        elif "/run" in systeminput:
            rpggame.execute()

        elif "/push" in systeminput:
            command = "/push"
            input_content = user_input_pre_command(systeminput, command) 
            push_command_parse_res: tuple[Optional[str], Optional[str]] = parse_target_and_message(input_content)
            if push_command_parse_res[0] is None or push_command_parse_res[1] is None:
                continue

            logger.debug(f"</force push command to {push_command_parse_res[0]}>:", input_content)
            ###
            gmcommandpush = GMCommandSimulateRequest("/push", rpggame, push_command_parse_res[0], push_command_parse_res[1])
            gmcommandpush.execute()
            ###
            logger.debug(f"{'=' * 50}")

        elif "/ask" in systeminput:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/ask"
            input_content = user_input_pre_command(systeminput, command)
            ask_command_parse_res: tuple[Optional[str], Optional[str]] = parse_target_and_message(input_content)
            if ask_command_parse_res[0] is None or ask_command_parse_res[1] is None:
                continue
            logger.debug(f"</ask command to {ask_command_parse_res[0]}>:", input_content)
            ###
            gmcommandask = GMCommandSimulateRequestThenRemoveConversation("/ask", rpggame, ask_command_parse_res[0], ask_command_parse_res[1])
            gmcommandask.execute()
            ###
            logger.debug(f"{'=' * 50}")

        elif "/who" in systeminput:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/who"
            bewho = user_input_pre_command(systeminput, command)
            ###
            playerproxy = get_player_proxy(TEST_PLAYER_NAME)
            assert playerproxy is not None
            playercommandbewho = GMCommandPlayerCtrlAnyNPC(command, rpggame, playerproxy, bewho)
            playercommandbewho.execute()
            ###            
            logger.debug(f"{'=' * 50}")

        if rpggame.exited:
            break
        
    rpggame.exit()


if __name__ == "__main__":
    main()