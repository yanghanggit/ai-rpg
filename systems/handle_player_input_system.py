from typing import override
from entitas import ExecuteProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from rpg_game import RPGGame 
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, PLAYER_INPUT_MODE, determine_player_input_mode
from dev_config import TEST_TERMINAL_NAME
from auxiliary.player_command import (
                          PlayerAttack, 
                          PlayerGoTo, 
                          PlayerBroadcast, 
                          PlayerSpeak,
                          PlayerUseProp, 
                          PlayerWhisper, 
                          PlayerSearch,
                          PlayerPortalStep,
                          PlayerSteal,
                          PlayerTrade, 
                          PlayerPerception,
                          PlayerCheckStatus)
from auxiliary.extended_context import ExtendedContext

############################################################################################################
def splitcommand(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val
############################################################################################################
class HandlePlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: RPGGame) -> None:
        self.context: ExtendedContext = context
        self.rpggame = rpggame
############################################################################################################
    @override
    def execute(self) -> None:
        # todo
        # 临时的设置，通过IP地址来判断是不是测试的客户端
        user_ips = self.rpggame.user_ips    
        # 判断，user_ips 与 self.context.user_ips 是否一致：元素的顺序和个数，和元素的内容
        # if user_ips != self.context.user_ips:
        #     assert False, "user_ips 与 self.context.user_ips 不一致"
    

        input_mode = determine_player_input_mode(user_ips)
        if input_mode == PLAYER_INPUT_MODE.WEB_HTTP_REQUEST:
            for playername in user_ips:
                self.play_via_client_and_handle_player_input(playername)
        elif input_mode == PLAYER_INPUT_MODE.TERMINAL:
            self.play_via_client_and_handle_player_input(TEST_TERMINAL_NAME)
        else:
            logger.error("未知的输入模式")
############################################################################################################
    def play_via_client_and_handle_player_input(self, playername: str) -> None:
        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.warning("玩家不存在，或者玩家未加入游戏")
            return
        
        for command in playerproxy._inputs:
            #todo
            singleplayer = self.context.get_player_entity(playername)
            assert singleplayer is not None
            #
            safename = self.context.safe_get_entity_name(singleplayer)
            playerproxy.add_actor_message(safename, command)
            
            ## 处理玩家的输入
            create_any_player_command_by_input = self.handle_input(self.rpggame, playerproxy, command)
            logger.debug(f"{'=' * 50}")

            if not create_any_player_command_by_input:
                ## 是立即模式，显示一下客户端的消息
                logger.debug("立即模式的input = " + command)     

            ## 总之要跳出循环 
            break
                  
        playerproxy._inputs.clear()
############################################################################################################
    def handle_input(self, rpggame: RPGGame, playerproxy: PlayerProxy, usrinput: str) -> bool:

        if "/quit" in usrinput:
            rpggame.exited = True
        
        elif "/attack" in usrinput:
            command = "/attack"
            targetname = splitcommand(usrinput, command)           
            PlayerAttack(command, rpggame, playerproxy, targetname).execute()
                        
        elif "/goto" in usrinput:
            command = "/goto"
            stagename = splitcommand(usrinput, command)
            PlayerGoTo(command, rpggame, playerproxy, stagename).execute()
  
        elif "/broadcast" in usrinput:
            command = "/broadcast"
            content = splitcommand(usrinput, command)
            PlayerBroadcast(command, rpggame, playerproxy, content).execute()
            
        elif "/speak" in usrinput:
            command = "/speak"
            content = splitcommand(usrinput, command)
            PlayerSpeak(command, rpggame, playerproxy, content).execute()

        elif "/whisper" in usrinput:
            command = "/whisper"
            content = splitcommand(usrinput, command)
            PlayerWhisper(command, rpggame,playerproxy, content).execute()

        elif "/search" in usrinput:
            command = "/search"
            propname = splitcommand(usrinput, command)
            PlayerSearch(command, rpggame, playerproxy, propname).execute()

        elif "/portalstep" in usrinput:
            command = "/portalstep"
            PlayerPortalStep(command, rpggame, playerproxy).execute()

        elif "/steal" in usrinput:
            command = "/steal"
            propname = splitcommand(usrinput, command)
            PlayerSteal(command, rpggame, playerproxy, propname).execute()

        elif "/trade" in usrinput:
            command = "/trade"
            propname = splitcommand(usrinput, command)
            PlayerTrade(command, rpggame, playerproxy, propname).execute()

        elif "/perception" in usrinput:
            command = "/perception"
            #self.imme_handle_perception(playerproxy)
            PlayerPerception(command, rpggame, playerproxy).execute()
            #return False

        elif "/checkstatus" in usrinput:
            command = "/checkstatus"
            #self.imme_handle_check_status(playerproxy)
            PlayerCheckStatus(command, rpggame, playerproxy).execute()
            #return False
        
        elif "/useprop" in usrinput:
            command = "/useprop"
            content = splitcommand(usrinput, command)
            PlayerUseProp(command, rpggame, playerproxy, content).execute()

        return True
############################################################################################################

