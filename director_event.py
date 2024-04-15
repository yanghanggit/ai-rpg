from auxiliary.extended_context import ExtendedContext
from auxiliary.prompt_maker import ( broadcast_action_prompt, 
speak_action_prompt,
__unique_prop_taken_away__, 
kill_someone,
attack_someone,
npc_leave_for_stage, 
npc_enter_stage, 
fail_to_exit_stage,
fail_to_enter_stage)
from loguru import logger
from auxiliary.print_in_color import Color
from abc import ABC, abstractmethod

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class IDirectorEvent(ABC):
    ### 这一步处理可以达到每个人看到的事件有不同的陈述，而不是全局唯一的陈述
    @abstractmethod
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        pass

    @abstractmethod
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        pass
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCBroadcastEvent(IDirectorEvent):
    def __init__(self, whobroadcast: str, stagename: str, content: str) -> None:
        self.whobroadcast = whobroadcast
        self.stagename = stagename
        self.content = content
    
    # 临时的
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.whobroadcast:
            logger.error(f"NPCBroadcastEvent => {npcname} vs {self.whobroadcast}")
        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content, extended_context)
        logger.info(f"{Color.HEADER}{broadcastcontent}{Color.ENDC}")
        return broadcastcontent
    
    # 临时的
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content, extended_context)
        logger.info(f"{Color.HEADER}{broadcastcontent}{Color.ENDC}")
        return broadcastcontent
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCSpeakEvent(IDirectorEvent):
    def __init__(self, whospeak: str, target: str, message: str) -> None:
        self.whospeak = whospeak
        self.target = target
        self.message = message

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.whospeak:
            logger.error(f"NPCSpeakEvent => {npcname} vs {self.whospeak}")
        speakcontent: str = speak_action_prompt(self.whospeak, self.target, self.message, extended_context)
        logger.info(f"{Color.HEADER}{speakcontent}{Color.ENDC}")
        return speakcontent
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        speakcontent: str = speak_action_prompt(self.whospeak, self.target, self.message, extended_context)
        logger.info(f"{Color.HEADER}{speakcontent}{Color.ENDC}")
        return speakcontent
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class NPCSearchFailedEvent(IDirectorEvent):
    def __init__(self, who_search_failed: str, target: str) -> None:
        self.who_search_failed = who_search_failed
        self.target = target

    #
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who_search_failed:
            logger.error(f"SearchFailedEvent => {npcname} vs {self.who_search_failed}")
        event = __unique_prop_taken_away__(self.who_search_failed, self.target)
        logger.info(event)
        return event
    
    #
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = __unique_prop_taken_away__(self.who_search_failed, self.target)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCKillSomeoneEvent(IDirectorEvent):
    def __init__(self, attacker: str, target: str) -> None:
        self.attacker = attacker
        self.target = target

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.attacker:
            logger.error(f"KillSomeoneEvent => {npcname} vs {self.attacker}")
        event = kill_someone(self.attacker, self.target)
        logger.info(event)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = kill_someone(self.attacker, self.target)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCAttackSomeoneEvent(IDirectorEvent):
    def __init__(self, attacker: str, target: str, damage: int, curhp: int, maxhp: int) -> None:
        self.attacker = attacker
        self.target = target
        self.damage = damage
        self.curhp = curhp
        self.maxhp = maxhp

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.attacker:
            logger.error(f"AttackSomeoneEvent => {npcname} vs {self.attacker}")
        event = attack_someone(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
        logger.info(event)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = attack_someone(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCLeaveForStageEvent(IDirectorEvent):
    def __init__(self, npc_name: str, current_stage_name: str, leave_for_stage_name: str) -> None:
        self.npc_name = npc_name
        self.current_stage_name = current_stage_name
        self.leave_for_stage_name = leave_for_stage_name

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npc_name:
            logger.error(f"LeaveForStageEvent => {npcname} vs {self.npc_name}")
        event = npc_leave_for_stage(self.npc_name, self.current_stage_name, self.leave_for_stage_name)
        logger.info(event)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = npc_leave_for_stage(self.npc_name, self.current_stage_name, self.leave_for_stage_name)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCEnterStageEvent(IDirectorEvent):
    def __init__(self, npc_name: str, stage_name: str) -> None:
        self.npc_name = npc_name
        self.stage_name = stage_name

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npc_name:
            logger.error(f"EnterStageEvent => {npcname} vs {self.npc_name}")
        event = npc_enter_stage(self.npc_name, self.stage_name)
        logger.info(event)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = npc_enter_stage(self.npc_name, self.stage_name)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCFailExitStageEvent(IDirectorEvent):
    def __init__(self, npc_name: str, stage_name: str, exit_condition: str) -> None:
        self.npc_name = npc_name
        self.stage_name = stage_name
        self.exit_condition = exit_condition

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npc_name:
            logger.error(f"FailExitStageEvent => {npcname} vs {self.npc_name}")
        event = fail_to_exit_stage(self.npc_name, self.stage_name, self.exit_condition)
        logger.info(event)
        return event 
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = fail_to_exit_stage(self.npc_name, self.stage_name, self.exit_condition)
        logger.info(event)
        return event 
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class NPCFailEnterStageEvent(IDirectorEvent):
    def __init__(self, npc_name: str, stage_name: str, enter_condition: str) -> None:
        self.npc_name = npc_name
        self.stage_name = stage_name
        self.enter_condition = enter_condition
  
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npc_name:
            logger.error(f"FailEnterStageEvent => {npcname} vs {self.npc_name}")
        event = fail_to_enter_stage(self.npc_name, self.stage_name, self.enter_condition)
        logger.info(event)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = fail_to_enter_stage(self.npc_name, self.stage_name, self.enter_condition)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 