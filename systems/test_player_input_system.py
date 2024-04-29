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
                          PlayerCommandWhisper, 
                          PlayerCommandSearch,
                          PlayerCommandPrisonBreak,
                          PlayerCommandPerception,
                          PlayerCommandSteal,
                          PlayerCommandTrade,
                          PlayerCommandCheckStatus)

from auxiliary.extended_context import ExtendedContext
from auxiliary.components import PlayerAwakeActionComponent, EnviroNarrateActionComponent
from auxiliary.actor_action import ActorAction
from typing import Optional

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

            # 客户端应该看到的
            self.clientdisplay(playerproxy)

            # 测试的客户端反馈
            usrinput = input(f"[{playername}]:")
            self.handle_player_input(self.rpggame, playerproxy, usrinput)
            logger.debug(f"{'=' * 50}")
            break
############################################################################################################
    #测试的先写死
    def current_input_player(self) -> str:
        return TEST_PLAYER_NAME
############################################################################################################ 
    def clientdisplay(self, playerproxy: PlayerProxy) -> None:
        playername = playerproxy.name
        playerentity = self.context.getplayer(playername)
        if playerentity is None:
            logger.error(f"showclient, 玩家不存在{playername}")
            return
        
        aboutgame = self.about_game_message(playerentity)
        if len(aboutgame) > 0:
            logger.error(f"<<<<<<<<<<<<<<<<<< [一个测试的游戏，模拟登陆的时候看到] >>>>>>>>>>>>>>>>>>")
            logger.error(f"{aboutgame}") 

        displaymsg = f"<<<<<<<<<<<<<<<<<< 你是玩家[{playername}] >>>>>>>>>>>>>>>>>>"
        # 常规的显示场景描述
        stagemsg = self.stagemessage(playerentity)
        if len(stagemsg) > 0:
            stageentity: Optional[Entity] = self.context.safe_get_stage_entity(playerentity)
            assert stageentity is not None
            stagename = self.context.safe_get_entity_name(stageentity)
            displaymsg += f"\n[{stagename}]=>{stagemsg}\n{'-' * 100}"

        # 如果是login，需要把login进入后的打印出来
        awakemsg = self.awakemessage(playerentity)     
        if len(awakemsg) > 0:
            npcname = self.context.safe_get_entity_name(playerentity)
            displaymsg += f"\n[{npcname}]=>{awakemsg}\n{'-' * 100}"
            
        #
        logger.warning(displaymsg)

############################################################################################################
    def about_game_message(self, playerentity: Entity) -> str:
        if not playerentity.has(PlayerAwakeActionComponent):
            return ""
        awakecomp: PlayerAwakeActionComponent = playerentity.get(PlayerAwakeActionComponent)
        action: ActorAction = awakecomp.action
        if len(action.values) == 0:
            return ""
        message = action.values[1]
        return message
############################################################################################################
    def awakemessage(self, playerentity: Entity) -> str:
        if not playerentity.has(PlayerAwakeActionComponent):
            return ""
        awakecomp: PlayerAwakeActionComponent = playerentity.get(PlayerAwakeActionComponent)
        action: ActorAction = awakecomp.action
        if len(action.values) == 0:
            return ""
        message = action.values[0]
        return message
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
    def handle_player_input(self, rpggame: RPGGame, playerproxy: PlayerProxy, usrinput: str) -> None:
        
        assert playerproxy is not None
        assert rpggame is not None

        if not rpggame.started:
            logger.warning("请先/run")
            return
        
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

        elif "/perception" in usrinput:
            command = "/perception"
            PlayerCommandPerception(command, rpggame, playerproxy).execute()
            logger.debug(f"{'=' * 50}")

        elif "/steal" in usrinput:
            command = "/steal"
            propname = splitcommand(usrinput, command)
            PlayerCommandSteal(command, rpggame, playerproxy, propname).execute()

        elif "/trade" in usrinput:
            command = "/trade"
            propname = splitcommand(usrinput, command)
            PlayerCommandTrade(command, rpggame, playerproxy, propname).execute()

        elif "/checkstatus" in usrinput:
            command = "/checkstatus"
            PlayerCommandCheckStatus(command, rpggame, playerproxy).execute()
############################################################################################################

