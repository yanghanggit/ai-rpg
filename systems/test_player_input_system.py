from entitas import ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from rpg_game import RPGGame 
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, TEST_PLAYER_NAME
from auxiliary.player_input_command import (
                          PlayerCommandAttack, 
                          PlayerCommandLeaveFor, 
                          PlayerCommandBroadcast, 
                          PlayerCommandSpeak, 
                          PlayerCommandWhisper, 
                          PlayerCommandSearch,
                          PlayerCommandPrisonBreak,
                          PlayerCommandPerception,
                          PlayerCommandSteal,
                          PlayerCommandTrade,
                          PlayerCommandCheckStatus)

from auxiliary.extended_context import ExtendedContext
#from rpg_game import RPGGame 

def split_command(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val

class TestPlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: 'RPGGame') -> None:
        self.context: ExtendedContext = context
        self.rpggame = rpggame
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  PlayerInputSystem  >>>>>>>>>>>>>>>>>")
        while True:
            playername = self.current_input_player()
            playerproxy = get_player_proxy(playername)
            if playerproxy is None:
                logger.warning("玩家不存在，或者玩家未加入游戏")
                break
            usrinput = input(f"[{playername}]:")
            rpggame = self.rpggame
            self.handle_player_input(rpggame, playerproxy, usrinput)
            break
############################################################################################################
    #测试的先写死
    def current_input_player(self) -> str:
        return TEST_PLAYER_NAME
############################################################################################################
    def handle_player_input(self, rpggame: RPGGame, playerproxy: PlayerProxy, usr_input: str) -> None:
        assert playerproxy is not None
        assert rpggame is not None
        if "/attack" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/attack"
            target_name = split_command(usr_input, command)    
            ###            
            playercommandattack = PlayerCommandAttack("/attack", rpggame, playerproxy, target_name)
            playercommandattack.execute()
            ###
            logger.debug(f"{'=' * 50}")
            
        elif "/leave" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/leave"
            target_name = split_command(usr_input, command)
            ###
            playercommandleavefor = PlayerCommandLeaveFor("/leave", rpggame, playerproxy, target_name)
            playercommandleavefor.execute()
            ###
            logger.debug(f"{'=' * 50}")
        
        elif "/broadcast" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/broadcast"
            content = split_command(usr_input, command)
            ###
            playercommandbroadcast = PlayerCommandBroadcast("/broadcast", rpggame, playerproxy, content)
            playercommandbroadcast.execute()
            ###
            logger.debug(f"{'=' * 50}")
            
        elif "/speak" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/speak"
            content = split_command(usr_input, command)
            ###
            playercommandspeak = PlayerCommandSpeak("/speak", rpggame, playerproxy, content)
            playercommandspeak.execute()
            ###
            logger.debug(f"{'=' * 50}")

        elif "/whisper" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/whisper"
            content = split_command(usr_input, command)
            ###
            playercommandwhisper = PlayerCommandWhisper("/whisper", rpggame,playerproxy, content)
            playercommandwhisper.execute()
            ###
            logger.debug(f"{'=' * 50}")
        
        elif "/search" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/search"
            content = split_command(usr_input, command)
            ###
            playercommandsearch = PlayerCommandSearch("/search", rpggame, playerproxy, content)
            playercommandsearch.execute()
            ###
            logger.debug(f"{'=' * 50}")

        elif "/prisonbreak" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/prisonbreak"
            playercommandprsionbreak = PlayerCommandPrisonBreak("/prisonbreak", rpggame, playerproxy)
            playercommandprsionbreak.execute()
            logger.debug(f"{'=' * 50}")

        elif "/perception" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            PlayerCommandPerception("/perception", rpggame, playerproxy).execute()
            logger.debug(f"{'=' * 50}")

        elif "/steal" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/steal"
            content = split_command(usr_input, command)
            PlayerCommandSteal("/steal", rpggame, playerproxy, content).execute()
            logger.debug(f"{'=' * 50}")

        elif "/trade" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            command = "/trade"
            content = split_command(usr_input, command)
            PlayerCommandTrade("/trade", rpggame, playerproxy, content).execute()
            logger.debug(f"{'=' * 50}")

        elif "/checkstatus" in usr_input:
            if not rpggame.started:
                logger.warning("请先/run")
                return
            PlayerCommandCheckStatus("/checkstatus", rpggame, playerproxy).execute()
            logger.debug(f"{'=' * 50}")
############################################################################################################

