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

############################################################################################################
def splitcommand(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val
############################################################################################################
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
            logger.debug(f"{'=' * 50}")
            break
############################################################################################################
    #测试的先写死
    def current_input_player(self) -> str:
        return TEST_PLAYER_NAME
############################################################################################################
    def handle_player_input(self, rpggame: RPGGame, playerproxy: PlayerProxy, usrinput: str) -> None:
        
        assert playerproxy is not None
        assert rpggame is not None

        if not rpggame.started:
            logger.warning("请先/run")
            return
        
        if "/attack" in usrinput:
            command = "/attack"
            target_name = splitcommand(usrinput, command)           
            playercommandattack = PlayerCommandAttack(command, rpggame, playerproxy, target_name)
            playercommandattack.execute()
                        
        elif "/leave" in usrinput:
            command = "/leave"
            target_name = splitcommand(usrinput, command)
            playercommandleavefor = PlayerCommandLeaveFor(command, rpggame, playerproxy, target_name)
            playercommandleavefor.execute()
  
        elif "/broadcast" in usrinput:
            command = "/broadcast"
            content = splitcommand(usrinput, command)
            playercommandbroadcast = PlayerCommandBroadcast(command, rpggame, playerproxy, content)
            playercommandbroadcast.execute()
            
        elif "/speak" in usrinput:
            command = "/speak"
            content = splitcommand(usrinput, command)
            playercommandspeak = PlayerCommandSpeak(command, rpggame, playerproxy, content)
            playercommandspeak.execute()

        elif "/whisper" in usrinput:
            command = "/whisper"
            content = splitcommand(usrinput, command)
            playercommandwhisper = PlayerCommandWhisper(command, rpggame,playerproxy, content)
            playercommandwhisper.execute()

        elif "/search" in usrinput:
            command = "/search"
            content = splitcommand(usrinput, command)
            playercommandsearch = PlayerCommandSearch(command, rpggame, playerproxy, content)
            playercommandsearch.execute()

        elif "/prisonbreak" in usrinput:
            command = "/prisonbreak"
            playercommandprsionbreak = PlayerCommandPrisonBreak(command, rpggame, playerproxy)
            playercommandprsionbreak.execute()

        elif "/perception" in usrinput:
            command = "/perception"
            PlayerCommandPerception(command, rpggame, playerproxy).execute()
            logger.debug(f"{'=' * 50}")

        elif "/steal" in usrinput:
            command = "/steal"
            content = splitcommand(usrinput, command)
            PlayerCommandSteal(command, rpggame, playerproxy, content).execute()

        elif "/trade" in usrinput:
            command = "/trade"
            content = splitcommand(usrinput, command)
            PlayerCommandTrade(command, rpggame, playerproxy, content).execute()

        elif "/checkstatus" in usrinput:
            command = "/checkstatus"
            PlayerCommandCheckStatus(command, rpggame, playerproxy).execute()
############################################################################################################

