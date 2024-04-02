import os
from typing import Optional
from loguru import logger
import datetime
from auxiliary.dialogue_rule import parse_command, parse_target_and_message_by_symbol
from auxiliary.world_data_builder import WorldDataBuilder
from rpg_game import RPGGame 
from player_proxy import PlayerProxy
from gm_input import GMCommandPush, GMCommandAsk, GMCommandLogChatHistory
from player_input import PlayerCommandBeWho, PlayerCommandAttack, PlayerCommandLeaveFor, PlayerCommandBroadcast, PlayerCommandSpeak, PlayerCommandWhisper, PlayerCommandSearch


### 临时的，写死创建budding_world
def read_world_data(worldname: str) -> Optional[WorldDataBuilder]:
    # 检查是否有存档
    # save_folder = f"./budding_world/saved_runtimes/{world_name}.json"
    # if not os.path.exists(save_folder):
       
    # else:
    #     world_data_path = save_folder

    #先写死！！！！
    version = 'ewan'
    runtimedir = f"./budding_world/gen_runtimes/"
    worlddata: str = f"{runtimedir}{worldname}.json"
    if not os.path.exists(worlddata):
        logger.error("未找到存档，请检查存档是否存在。")
        return None

    createworld: Optional[WorldDataBuilder] = WorldDataBuilder(worldname, version, runtimedir)
    if createworld is None:
        logger.error("WorldDataBuilder初始化失败。")
        return None
    
    if not createworld.check_version_valid(worlddata):
        logger.error("World.json版本不匹配，请检查版本号。")
        return None
    
    createworld.build()
    return createworld

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
def main() -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    worldname = input("请输入要进入的世界名称(必须与自动化创建的名字一致):")
    worlddata = read_world_data(worldname)
    if worlddata is None:
        logger.error("create_world_data_builder 失败。")
        return

    # 创建必要的变量
    rpggame = RPGGame(worldname)
    rpggame.createworld(worlddata)
    playproxy = PlayerProxy("yanghang")

    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            break

        elif "/run" in usr_input:
            #顺序不要动！！！！！！！！！
            rpggame.execute()

        elif "/push" in usr_input:
            command = "/push"
            input_content = parse_command(usr_input, command) 
            push_command_parse_res: tuple[str, str] = parse_target_and_message_by_symbol(input_content)
            logger.debug(f"</force push command to {push_command_parse_res[0]}>:", input_content)
            ###
            gmcommandpush = GMCommandPush("/push", rpggame, push_command_parse_res[0], push_command_parse_res[1])
            gmcommandpush.execute()
            ###
            logger.debug(f"{'=' * 50}")

        elif "/ask" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/ask"
            input_content = parse_command(usr_input, command)
            ask_command_parse_res: tuple[str, str] = parse_target_and_message_by_symbol(input_content)
            logger.debug(f"</ask command to {ask_command_parse_res[0]}>:", input_content)
            ###
            gmcommandask = GMCommandAsk("/ask", rpggame, ask_command_parse_res[0], ask_command_parse_res[1])
            gmcommandask.execute()
            ###
            logger.debug(f"{'=' * 50}")

        elif "/showstages" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/showstages"
            who = parse_command(usr_input, command)
            ###
            log = rpggame.extendedcontext.information_about_all_stages_and_npcs()
            ###
            logger.debug(f"/showstages: \n{log}")
            logger.debug(f"{'=' * 50}")

        elif "/who" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/who"
            who = parse_command(usr_input, command)
            ###
            playercommandbewho = PlayerCommandBeWho("/who", rpggame, playproxy, who)
            playercommandbewho.execute()
            ###            
            logger.debug(f"{'=' * 50}")
           
        elif "/attack" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/attack"
            target_name = parse_command(usr_input, command)    
            ###
            playercommandattack = PlayerCommandAttack("/attack", rpggame, playproxy, target_name)
            playercommandattack.execute()
            ###
            logger.debug(f"{'=' * 50}")
        
        elif "/mem" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/mem"
            target_name = parse_command(usr_input, command)
            ###
            gmcommandlogchathistory = GMCommandLogChatHistory("/mem", rpggame, target_name)
            gmcommandlogchathistory.execute()
            ###
            logger.debug(f"{'=' * 50}")
        
        elif "/leave" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/leave"
            target_name = parse_command(usr_input, command)
            ###
            playercommandleavefor = PlayerCommandLeaveFor("/leave", rpggame, playproxy, target_name)
            playercommandleavefor.execute()
            ###
            logger.debug(f"{'=' * 50}")
        
        elif "/broadcast" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/broadcast"
            content = parse_command(usr_input, command)
            ###
            playercommandbroadcast = PlayerCommandBroadcast("/broadcast", rpggame, playproxy, content)
            playercommandbroadcast.execute()
            ###
            logger.debug(f"{'=' * 50}")
            
        elif "/speak" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/speak"
            content = parse_command(usr_input, command)
            ###
            playercommandspeak = PlayerCommandSpeak("/speak", rpggame, playproxy, content)
            playercommandspeak.execute()
            ###
            logger.debug(f"{'=' * 50}")

        elif "/whisper" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/whisper"
            content = parse_command(usr_input, command)
            ###
            playercommandwhisper = PlayerCommandWhisper("/whisper", rpggame, playproxy, content)
            playercommandwhisper.execute()
            ###
            logger.debug(f"{'=' * 50}")
        
        elif "/search" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/search"
            content = parse_command(usr_input, command)
            ###
            playercommandsearch = PlayerCommandSearch("/search", rpggame, playproxy, content)
            playercommandsearch.execute()
            ###
            logger.debug(f"{'=' * 50}")

    rpggame.exit()


if __name__ == "__main__":
    main()