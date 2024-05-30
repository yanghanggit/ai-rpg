from entitas import ExecuteProcessor#type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from rpg_game import RPGGame 
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, TEST_TERMINAL_NAME, PLAYER_INPUT_MODE, determine_player_input_mode
from auxiliary.player_input_command import (
                          PlayerCommandAttack, 
                          PlayerCommandLeaveFor, 
                          PlayerCommandBroadcast, 
                          PlayerCommandSpeak,
                          PlayerCommandUseInteractiveProp, 
                          PlayerCommandWhisper, 
                          PlayerCommandSearch,
                          PlayerCommandPrisonBreak,
                          PlayerCommandSteal,
                          PlayerCommandTrade, 
                          PlayerCommandPerception,
                          PlayerCommandCheckStatus)

from auxiliary.extended_context import ExtendedContext
from systems.check_status_action_system import CheckStatusActionHelper, NPCCheckStatusEvent
from systems.perception_action_system import PerceptionActionHelper, NPCPerceptionEvent


############################################################################################################
def splitcommand(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val
############################################################################################################
class HandlePlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: 'RPGGame') -> None:
        self.context: ExtendedContext = context
        self.rpggame = rpggame
############################################################################################################
    def execute(self) -> None:
        # 临时的设置，通过IP地址来判断是不是测试的客户端
        playername = self.context.user_ip
        input_mode = determine_player_input_mode(playername)
        if input_mode == PLAYER_INPUT_MODE.WEB_HTTP_REQUEST:
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
        
        for command in playerproxy.commands:
            #todo
            singleplayer = self.context.getplayer(playername)
            assert singleplayer is not None
            #
            safename = self.context.safe_get_entity_name(singleplayer)
            playerproxy.add_npc_message(safename, command)
            
            ## 处理玩家的输入
            create_any_player_command_by_input = self.handle_input(self.rpggame, playerproxy, command)
            logger.debug(f"{'=' * 50}")

            if not create_any_player_command_by_input:
                ## 是立即模式，显示一下客户端的消息
                logger.debug("立即模式的input = " + command)     

            ## 总之要跳出循环 
            break
                  
        playerproxy.commands.clear()
############################################################################################################
    def handle_input(self, rpggame: RPGGame, playerproxy: PlayerProxy, usrinput: str) -> bool:

        if "/quit" in usrinput:
            rpggame.exited = True
        
        elif "/attack" in usrinput:
            command = "/attack"
            targetname = splitcommand(usrinput, command)           
            PlayerCommandAttack(command, rpggame, playerproxy, targetname).execute()
                        
        elif "/leave" in usrinput:
            command = "/leave"
            stagename = splitcommand(usrinput, command)
            PlayerCommandLeaveFor(command, rpggame, playerproxy, stagename).execute()
  
        elif "/broadcast" in usrinput:
            command = "/broadcast"
            content = splitcommand(usrinput, command)
            PlayerCommandBroadcast(command, rpggame, playerproxy, content).execute()
            
        elif "/speak" in usrinput:
            command = "/speak"
            content = splitcommand(usrinput, command)
            PlayerCommandSpeak(command, rpggame, playerproxy, content).execute()

        elif "/whisper" in usrinput:
            command = "/whisper"
            content = splitcommand(usrinput, command)
            PlayerCommandWhisper(command, rpggame,playerproxy, content).execute()

        elif "/search" in usrinput:
            command = "/search"
            propname = splitcommand(usrinput, command)
            PlayerCommandSearch(command, rpggame, playerproxy, propname).execute()

        elif "/prisonbreak" in usrinput:
            command = "/prisonbreak"
            PlayerCommandPrisonBreak(command, rpggame, playerproxy).execute()

        elif "/steal" in usrinput:
            command = "/steal"
            propname = splitcommand(usrinput, command)
            PlayerCommandSteal(command, rpggame, playerproxy, propname).execute()

        elif "/trade" in usrinput:
            command = "/trade"
            propname = splitcommand(usrinput, command)
            PlayerCommandTrade(command, rpggame, playerproxy, propname).execute()

        elif "/perception" in usrinput:
            command = "/perception"
            #self.imme_handle_perception(playerproxy)
            PlayerCommandPerception(command, rpggame, playerproxy).execute()
            #return False

        elif "/checkstatus" in usrinput:
            command = "/checkstatus"
            #self.imme_handle_check_status(playerproxy)
            PlayerCommandCheckStatus(command, rpggame, playerproxy).execute()
            #return False
        
        elif "/useprop" in usrinput:
            command = "/useprop"
            content = splitcommand(usrinput, command)
            PlayerCommandUseInteractiveProp(command, rpggame, playerproxy, content).execute()

        return True
############################################################################################################
#     def imme_handle_perception(self, playerproxy: PlayerProxy) -> None:
#         playerentity = self.context.getplayer(playerproxy.name)
#         if playerentity is None:
#             return
#         #
#         helper = PerceptionActionHelper(self.context)
#         helper.perception(playerentity)
#         #
#         safe_npc_name = self.context.safe_get_entity_name(playerentity)
#         stageentity = self.context.safe_get_stage_entity(playerentity)
#         assert stageentity is not None
#         safe_stage_name = self.context.safe_get_entity_name(stageentity)
#         #
#         event = NPCPerceptionEvent(safe_npc_name, safe_stage_name, helper.npcs_in_stage, helper.props_in_stage)
#         message = event.tonpc(safe_npc_name, self.context)
#         #
#         playerproxy.add_npc_message(safe_npc_name, message)
# ############################################################################################################
#     def imme_handle_check_status(self, playerproxy: PlayerProxy) -> None:
#         playerentity = self.context.getplayer(playerproxy.name)
#         if playerentity is None:
#             return
#         #
#         helper = CheckStatusActionHelper(self.context)
#         helper.check_status(playerentity)
#         #
#         safename = self.context.safe_get_entity_name(playerentity)
#         #
#         event = NPCCheckStatusEvent(safename, helper.props, helper.health, helper.role_components, helper.events)
#         message = event.tonpc(safename, self.context)
#         playerproxy.add_npc_message(safename, message)
############################################################################################################

