from auxiliary.extended_context import ExtendedContext
from auxiliary.cn_builtin_prompt import ( broadcast_action_prompt, 
speak_action_prompt,
kill_someone,
attack_someone_prompt,
steal_action_prompt,
trade_action_prompt,
leave_for_stage_failed_because_stage_is_invalid_prompt,
leave_for_stage_failed_because_already_in_stage_prompt,
whisper_action_prompt,
interactive_prop_action_success_prompt)
from loguru import logger
from abc import ABC, abstractmethod
from typing import List, Dict
from auxiliary.base_data import PropData

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
### 这一步处理可以达到每个人看到的事件有不同的陈述，而不是全局唯一的陈述
class IDirectorEvent(ABC):
    @abstractmethod
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        pass

    @abstractmethod
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        pass
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class BroadcastEvent(IDirectorEvent):

    def __init__(self, whobroadcast: str, stagename: str, content: str) -> None:
        self.whobroadcast = whobroadcast
        self.stagename = stagename
        self.content = content
    
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content, extended_context)
        return broadcastcontent
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content, extended_context)
        return broadcastcontent
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class SpeakEvent(IDirectorEvent):

    def __init__(self, who_is_speaking: str, who_is_target: str, message: str) -> None:
        self.who_is_speaking = who_is_speaking
        self.who_is_target = who_is_target
        self.message = message

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        speakcontent: str = speak_action_prompt(self.who_is_speaking, self.who_is_target, self.message, extended_context)
        return speakcontent
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        speakcontent: str = speak_action_prompt(self.who_is_speaking, self.who_is_target, self.message, extended_context)
        return speakcontent
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCKillSomeoneEvent(IDirectorEvent):
    
    def __init__(self, attacker: str, target: str) -> None:
        self.attacker = attacker
        self.target = target

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        event = kill_someone(self.attacker, self.target)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = kill_someone(self.attacker, self.target)
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
        event = attack_someone_prompt(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = attack_someone_prompt(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
        return event
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class WhisperEvent(IDirectorEvent):
    
    def __init__(self, who_is_whispering: str, who_is_target: str, message: str) -> None:
        self.who_is_whispering = who_is_whispering
        self.who_is_target = who_is_target
        self.message = message

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who_is_whispering or npcname != self.who_is_target:
            # 只有这2个人才能听到
            return ""
        whispercontent = whisper_action_prompt(self.who_is_whispering, self.who_is_target, self.message, extended_context)
        return whispercontent
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        ## 场景应该是彻底听不到
        return ""

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCStealEvent(IDirectorEvent):

    def __init__(self, whosteal: str, targetname: str, propname: str, stealres: bool) -> None:
        self.whosteal = whosteal
        self.targetname = targetname
        self.propname = propname
        self.stealres = stealres
       
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.whosteal or npcname != self.targetname:
            return ""
        
        stealcontent = steal_action_prompt(self.whosteal, self.targetname, self.propname, self.stealres)
        return stealcontent
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCTradeEvent(IDirectorEvent):

    def __init__(self, fromwho: str, towho: str, propname: str, traderes: bool) -> None:
        self.fromwho = fromwho
        self.towho = towho
        self.propname = propname
        self.traderes = traderes

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.fromwho or npcname != self.towho:
            return ""
        
        tradecontent = trade_action_prompt(self.fromwho, self.towho, self.propname, self.traderes)
        return tradecontent
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""

####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCLeaveForFailedBecauseStageIsInvalidEvent(IDirectorEvent):

    def __init__(self, npcname: str, stagename: str) -> None:
        self.npcname = npcname
        self.stagename = stagename

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npcname:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        leave_for_stage_is_invalid_event = leave_for_stage_failed_because_stage_is_invalid_prompt(self.npcname, self.stagename)
        return leave_for_stage_is_invalid_event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCLeaveForFailedBecauseAlreadyInStage(IDirectorEvent):

    def __init__(self, npcname: str, stagename: str) -> None:
        self.npcname = npcname
        self.stagename = stagename

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npcname:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        already_in_stage_event = leave_for_stage_failed_because_already_in_stage_prompt(self.npcname, self.stagename)
        return already_in_stage_event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCInteractivePropEvent(IDirectorEvent):

    def __init__(self, npcname: str, targetname: str, propname: str) -> None:
        self.npcname = npcname
        self.targetname = targetname
        self.propname = propname

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        return interactive_prop_action_success_prompt(self.npcname, self.targetname, self.propname)
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return interactive_prop_action_success_prompt(self.npcname, self.targetname, self.propname)








