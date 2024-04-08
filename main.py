import os
from typing import Optional
from loguru import logger
import datetime
from auxiliary.dialogue_rule import parse_command, parse_target_and_message_by_symbol
from auxiliary.builders import WorldDataBuilder
from rpg_game import RPGGame 
from player_proxy import PlayerProxy
from gm_input import GMCommandPush, GMCommandAsk, GMCommandLogChatHistory
from player_input import (PlayerCommandCtrlNPC, 
                          PlayerCommandAttack, 
                          PlayerCommandLeaveFor, 
                          PlayerCommandBroadcast, 
                          PlayerCommandSpeak, 
                          PlayerCommandWhisper, 
                          PlayerCommandSearch,
                          PlayerCommandLogin)

from auxiliary.extended_context import ExtendedContext
from auxiliary.file_system import FileSystem
from auxiliary.memory_system import MemorySystem
from typing import Optional
from auxiliary.agent_connect_system import AgentConnectSystem
from auxiliary.code_name_component_system import CodeNameComponentSystem


### 临时的，写死创建budding_world
def read_world_data(worldname: str) -> Optional[WorldDataBuilder]:
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

##
def create_rpg_game(worldname: str) -> RPGGame:

    # 依赖注入的特殊系统
    file_system = FileSystem("file_system， Because it involves IO operations, an independent system is more convenient.")
    memory_system = MemorySystem("memorey_system， Because it involves IO operations, an independent system is more convenient.")
    agent_connect_system = AgentConnectSystem("agent_connect_system， Because it involves net operations, an independent system is more convenient.")
    code_name_component_system = CodeNameComponentSystem("Build components by codename for special purposes")

    # 创建上下文
    context = ExtendedContext(file_system, memory_system, agent_connect_system, code_name_component_system)

    # 创建游戏
    rpggame = RPGGame(worldname, context)
    return rpggame

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
def main() -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    # 读取世界资源文件
    worldname = input("请输入要进入的世界名称(必须与自动化创建的名字一致):")
    worlddata = read_world_data(worldname)
    if worlddata is None:
        logger.error("create_world_data_builder 失败。")
        return
    
    # 创建游戏
    rpggame = create_rpg_game(worldname)
    if rpggame is None:
        logger.error("create_rpg_game 失败。")
        return
    
    # 创建世界
    rpggame.createworld(worlddata)
    
    # 测试的代码，上来就控制一个NPC目标，先写死"无名旅人"
    playproxy = PlayerProxy("yanghang")
    playerstartcmd = PlayerCommandLogin("/player-login", rpggame, playproxy, "无名旅人")
    playerstartcmd.execute()

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

        elif "/who" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                continue
            command = "/who"
            who = parse_command(usr_input, command)
            ###
            playercommandbewho = PlayerCommandCtrlNPC("/who", rpggame, playproxy, who)
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