from entitas import ExecuteProcessor, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from rpg_game import RPGGame 
from auxiliary.player_proxy import PlayerProxy, get_player_proxy, TEST_PLAYER_NAME, TEST_GAME_INSTRUCTIONS_WHEN_LOGIN_SUCCESS_FOR_FIRST_TIME, TEST_LOGIN_INFORMATION
from auxiliary.player_input_command import (
                          PlayerCommandAttack, 
                          PlayerCommandLeaveFor, 
                          PlayerCommandBroadcast, 
                          PlayerCommandSpeak,
                          PlayerCommandInteractiveProp, 
                          PlayerCommandWhisper, 
                          PlayerCommandSearch,
                          PlayerCommandPrisonBreak,
                          PlayerCommandPerception,
                          PlayerCommandSteal,
                          PlayerCommandTrade,
                          PlayerCommandCheckStatus)

from auxiliary.extended_context import ExtendedContext
from auxiliary.components import PlayerLoginEventComponent, EnviroNarrateActionComponent
from auxiliary.actor_action import ActorAction
from typing import Optional
from systems.check_status_action_system import CheckStatusActionHelper
from systems.perception_action_system import PerceptionActionHelper
from auxiliary.director_event import NPCPerceptionEvent, NPCCheckStatusEvent

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
        playername = self.current_input_player()
        self.handlelogin(playername) ## 只有登陆的时候特殊处理
        self.handlenormal(playername) ## 日常的处理
        self.handleinput(playername) ## 核心输入，while循环
        self.postexecute(playername) ## 最后的处理，会删掉PlayerLoginEventComponent
############################################################################################################
    def postexecute(self, playername: str) -> None:
        playerentity = self.context.getplayer(playername)
        if playerentity is None:
            #logger.error(f"handlelogin, 玩家不存在{playername}")
            return
        #登陆成功后，需要删除这个组件
        if playerentity.has(PlayerLoginEventComponent):
            playerentity.remove(PlayerLoginEventComponent)
            logger.debug(f"handlelogin {playername} success")
############################################################################################################
    #测试的先写死
    def current_input_player(self) -> str:
        return TEST_PLAYER_NAME
############################################################################################################
    def handlelogin(self, playername: str) -> None:
        #
        context = self.context
        memory_system = context.memory_system
        #
        playerentity = self.context.getplayer(playername)
        if playerentity is None:
            #logger.error(f"handlelogin, 玩家不存在{playername}")
            return
        
        if not playerentity.has(PlayerLoginEventComponent):
            # 不需要处理
            return
        
        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.error(f"handlelogin, 玩家代理不存在{playername}")
            return
        
        #登陆的消息
        playerproxy.add_system_message(TEST_LOGIN_INFORMATION)
        
        #打印关于游戏的信息
        playerproxy.add_system_message(TEST_GAME_INSTRUCTIONS_WHEN_LOGIN_SUCCESS_FOR_FIRST_TIME)

        #初始化的NPC记忆
        safename = context.safe_get_entity_name(playerentity)
        initmemory =  memory_system.getmemory(safename)
        playerproxy.add_npc_message(safename, initmemory)
            
        #此时场景的描述
        stagemsg = self.stagemessage(playerentity)
        if len(stagemsg) > 0:
            stageentity: Optional[Entity] = self.context.safe_get_stage_entity(playerentity)
            assert stageentity is not None
            stagename = self.context.safe_get_entity_name(stageentity)
            playerproxy.add_stage_message(stagename, stagemsg)
############################################################################################################
    def handlenormal(self, playername: str) -> None:
        #
        playerentity = self.context.getplayer(playername)
        if playerentity is None:
            #logger.error(f"handlelogin, 玩家不存在{playername}")
            return
        
        if playerentity.has(PlayerLoginEventComponent):
            # 不需要处理
            return
    
        playerproxy = get_player_proxy(playername)
        if playerproxy is None:
            logger.error(f"handlelogin, 玩家代理不存在{playername}")
            return
            
        #此时场景的描述
        stagemsg = self.stagemessage(playerentity)
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
            self.client_display_messages(playerproxy, 10)
            
            # 测试的客户端反馈
            usrinput = input(f"[{playername}]:")
            if self.playerinput(self.rpggame, playerproxy, usrinput):
                logger.debug(f"{'=' * 50}")
                break
############################################################################################################ 
    def client_display_messages(self, playerproxy: PlayerProxy, display_messages_count: int) -> None:
        clientmessages = playerproxy.clientmessages
        for message in clientmessages[-display_messages_count:]:
            tag = message[0]
            content = message[1]
            logger.warning(f"{tag}=>{content}")
############################################################################################################
    def stagemessage(self, playerentity: Entity) -> str:
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
        
        if "/attack" in usrinput:
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
            PlayerCommandInteractiveProp(command, rpggame, playerproxy, content).execute()
            return False

        return True
############################################################################################################
    def imme_handle_perception(self, playerproxy: PlayerProxy) -> None:
        playerentity = self.context.getplayer(playerproxy.name)
        if playerentity is None:
            return
        #
        helper = PerceptionActionHelper(self.context)
        npcs_in_stage = helper.perception_npcs_in_stage(playerentity)
        props_in_stage = helper.perception_props_in_stage(playerentity)
        #
        safe_npc_name = self.context.safe_get_entity_name(playerentity)
        stageentity = self.context.safe_get_stage_entity(playerentity)
        assert stageentity is not None
        safe_stage_name = self.context.safe_get_entity_name(stageentity)
        #
        event = NPCPerceptionEvent(safe_npc_name, safe_stage_name, npcs_in_stage, props_in_stage)
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
        helper.handle(playerentity)
        propnames = helper.propnames
        prop_and_desc = helper.prop_and_desc
        safename = self.context.safe_get_entity_name(playerentity)
        #
        event = NPCCheckStatusEvent(safename, propnames, prop_and_desc)
        message = event.tonpc(safename, self.context)
        playerproxy.add_npc_message(safename, message)
############################################################################################################

