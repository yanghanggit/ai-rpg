from entitas import ExecuteProcessor#type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
#from rpg_game import RPGGame 
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, TEST_TERMINAL_NAME, PLAYER_INPUT_MODE, determine_player_input_mode
from auxiliary.extended_context import ExtendedContext
from systems.check_status_action_system import CheckStatusActionHelper, NPCCheckStatusEvent
from systems.perception_action_system import PerceptionActionHelper, NPCPerceptionEvent
from typing import Any, cast


############################################################################################################
class TerminalPlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext, rpggame: Any) -> None:
        self.context: ExtendedContext = context
        self.rpggame = rpggame
############################################################################################################
    def execute(self) -> None:
        # 临时的设置，通过IP地址来判断是不是测试的客户端
        playername = self.context.user_ip
        input_mode = determine_player_input_mode(playername)
        if input_mode == PLAYER_INPUT_MODE.TERMINAL:
            self.play_via_terminal_and_handle_player_input(TEST_TERMINAL_NAME)
        else:
            logger.debug("只处理终端的输入")
############################################################################################################
    def play_via_terminal_and_handle_player_input(self, playername: str) -> None:
        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.warning("玩家不存在，或者玩家未加入游戏")
            return
        while True:
            # 客户端应该看到的
            self.display_client_messages(playerproxy, 10)    
            # 测试的客户端反馈
            usrinput = input(f"[{playername}]:")
            playerproxy.add_system_message(usrinput)
            if self.playerinput(self.rpggame, playerproxy, usrinput):
                logger.debug(f"{'=' * 50}")
                break
############################################################################################################ 
    def display_client_messages(self, playerproxy: PlayerProxy, display_messages_count: int) -> None:
        clientmessages = playerproxy.clientmessages
        for message in clientmessages[-display_messages_count:]:
            tag = message[0]
            content = message[1]
            logger.warning(f"{tag}=>{content}")
############################################################################################################
    def playerinput(self, rpggame: Any, playerproxy: PlayerProxy, usrinput: str) -> bool:

        if "/quit" in usrinput:
            #rpggame.exited = True
            from rpg_game import RPGGame 
            cast(RPGGame, rpggame).exit()

        elif "/perception" in usrinput:
            # player 执行立即模式
            command = "/perception"
            self.imme_handle_perception(playerproxy)
            #PlayerCommandPerception(command, rpggame, playerproxy).execute()
            return False

        elif "/checkstatus" in usrinput:
            # player 执行立即模式
            command = "/checkstatus"
            self.imme_handle_check_status(playerproxy)
            #PlayerCommandCheckStatus(command, rpggame, playerproxy).execute()
            return False
        else:
            playerproxy.commands.append(str(usrinput))
            
        return True
############################################################################################################
    def imme_handle_perception(self, playerproxy: PlayerProxy) -> None:
        playerentity = self.context.getplayer(playerproxy.name)
        if playerentity is None:
            return
        #
        helper = PerceptionActionHelper(self.context)
        helper.perception(playerentity)
        #
        safe_npc_name = self.context.safe_get_entity_name(playerentity)
        stageentity = self.context.safe_get_stage_entity(playerentity)
        assert stageentity is not None
        safe_stage_name = self.context.safe_get_entity_name(stageentity)
        #
        event = NPCPerceptionEvent(safe_npc_name, safe_stage_name, helper.npcs_in_stage, helper.props_in_stage)
        message = event.tonpc(safe_npc_name, self.context)
        #
        playerproxy.add_npc_message(safe_npc_name, message)
############################################################################################################
    def imme_handle_check_status(self, playerproxy: PlayerProxy) -> None:
        playerentity = self.context.getplayer(playerproxy.name)
        if playerentity is None:
            return
        #
        helper = CheckStatusActionHelper(self.context)
        helper.check_status(playerentity)
        #
        safename = self.context.safe_get_entity_name(playerentity)
        #
        event = NPCCheckStatusEvent(safename, helper.props, helper.health, helper.role_components, helper.events)
        message = event.tonpc(safename, self.context)
        playerproxy.add_npc_message(safename, message)
############################################################################################################

