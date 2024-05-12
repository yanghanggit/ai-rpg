from entitas import ExecuteProcessor, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from rpg_game import RPGGame 
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, TEST_PLAYER_NAME
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
                          PlayerCommandTrade)

from auxiliary.extended_context import ExtendedContext
from auxiliary.components import EnviroNarrateActionComponent
from auxiliary.actor_action import ActorAction
from typing import Optional
from systems.check_status_action_system import CheckStatusActionHelper, NPCCheckStatusEvent
from systems.perception_action_system import PerceptionActionHelper, NPCPerceptionEvent

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
        playername = TEST_PLAYER_NAME#self.current_input_player()
        #self.handlelogin(playername) ## 只有登陆的时候特殊处理
        self.add_player_client_message(playername) ## 日常的处理
        self.handleinput(playername) ## 核心输入，while循环
        #self.postexecute(playername) ## 最后的处理，会删掉PlayerLoginEventComponent
############################################################################################################
    def add_player_client_message(self, playername: str) -> None:
        #
        playerentity = self.context.getplayer(playername)
        if playerentity is None:
            #logger.error(f"handlelogin, 玩家不存在{playername}")
            return

        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.error(f"handlelogin, 玩家代理不存在{playername}")
            return
            
        #此时场景的描述
        stagemsg = self.current_stage_message(playerentity)
        if len(stagemsg) > 0:
            stageentity: Optional[Entity] = self.context.safe_get_stage_entity(playerentity)
            assert stageentity is not None
            stagename = self.context.safe_get_entity_name(stageentity)
            playerproxy.add_stage_message(stagename, stagemsg)
############################################################################################################
    def handleinput(self, playername: str) -> None:
        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.warning("玩家不存在，或者玩家未加入游戏")
            return

        while True:
            if not self.rpggame.started:
                logger.warning("请先/run")
                break
            
            # 客户端应该看到的
            self.display_player_client_messages(playerproxy, 10)
            
            # 测试的客户端反馈
            usrinput = input(f"[{playername}]:")
            playerproxy.add_system_message(usrinput)
            if self.playerinput(self.rpggame, playerproxy, usrinput):
                logger.debug(f"{'=' * 50}")
                break
############################################################################################################ 
    def display_player_client_messages(self, playerproxy: PlayerProxy, display_messages_count: int) -> None:
        clientmessages = playerproxy.clientmessages
        for message in clientmessages[-display_messages_count:]:
            tag = message[0]
            content = message[1]
            logger.warning(f"{tag}=>{content}")
############################################################################################################
    def current_stage_message(self, playerentity: Entity) -> str:
        stage = self.context.safe_get_stage_entity(playerentity)
        if stage is None:
            return ""
        if not stage.has(EnviroNarrateActionComponent):
            return ""

        envirocomp: EnviroNarrateActionComponent = stage.get(EnviroNarrateActionComponent)
        action: ActorAction = envirocomp.action
        if len(action.values) == 0:
            return ""
        message = action.values[0]
        return message
############################################################################################################
    def playerinput(self, rpggame: RPGGame, playerproxy: PlayerProxy, usrinput: str) -> bool:

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
            self.imme_handle_perception(playerproxy)
            #PlayerCommandPerception(command, rpggame, playerproxy).execute()
            return False

        elif "/checkstatus" in usrinput:
            command = "/checkstatus"
            self.imme_handle_check_status(playerproxy)
            #PlayerCommandCheckStatus(command, rpggame, playerproxy).execute()
            return False
        
        elif "/useprop" in usrinput:
            command = "/useprop"
            content = splitcommand(usrinput, command)
            PlayerCommandUseInteractiveProp(command, rpggame, playerproxy, content).execute()
            #return False

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

