from auxiliary.extended_context import ExtendedContext
from auxiliary.cn_builtin_prompt import ( broadcast_action_prompt, 
speak_action_prompt,
search_failed_prompt, 
kill_someone,
attack_someone_prompt,
npc_leave_stage_prompt, 
notify_all_already_in_target_stage_that_someone_enter_stage_prompt, 
steal_action_prompt,
trade_action_prompt,
leave_for_stage_failed_because_stage_is_invalid_prompt,
leave_for_stage_failed_because_already_in_stage_prompt,
whisper_action_prompt,
leave_for_stage_failed_because_no_exit_condition_match_prompt,
search_success_prompt,
notify_myself_leave_for_from_prompt,
someone_came_into_my_stage_his_appearance_prompt,
npc_appearance_in_this_stage_prompt,
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
class NPCSearchFailedEvent(IDirectorEvent):

    def __init__(self, who_search_failed: str, target: str) -> None:
        self.who_search_failed = who_search_failed
        self.target = target

    #
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who_search_failed:
            ## 只有自己知道
            return ""
        event = search_failed_prompt(self.who_search_failed, self.target)
        return event
    
    #
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = search_failed_prompt(self.who_search_failed, self.target)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class NPCSearchSuccessEvent(IDirectorEvent):

    #
    def __init__(self, who_search_success: str, target: str, stagename: str) -> None:
        self.who_search_success = who_search_success
        self.target = target
        self.stagename = stagename

    #
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who_search_success:
            ## 只有自己知道
            return ""
        event = search_success_prompt(self.who_search_success, self.target, self.stagename)
        return event
    
    #
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = search_success_prompt(self.who_search_success, self.target, self.stagename)
        return event
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
class NPCLeaveStageEvent(IDirectorEvent):

    def __init__(self, npc_name: str, current_stage_name: str, leave_for_stage_name: str) -> None:
        self.npc_name = npc_name
        self.current_stage_name = current_stage_name
        self.leave_for_stage_name = leave_for_stage_name

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        event = npc_leave_stage_prompt(self.npc_name, self.current_stage_name, self.leave_for_stage_name)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = npc_leave_stage_prompt(self.npc_name, self.current_stage_name, self.leave_for_stage_name)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCEnterStageEvent(IDirectorEvent):

    def __init__(self, npc_name: str, stage_name: str, last_stage_name: str) -> None:
        self.npc_name = npc_name
        self.stage_name = stage_name
        self.last_stage_name = last_stage_name

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npc_name:
            # 目标场景内的一切听到的是这个:"xxx进入了场景"
            return notify_all_already_in_target_stage_that_someone_enter_stage_prompt(self.npc_name, self.stage_name, self.last_stage_name)
            
        #通知我自己，我从哪里去往了哪里。这样prompt更加清晰一些
        return notify_myself_leave_for_from_prompt(self.npc_name, self.stage_name, self.last_stage_name)
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = notify_all_already_in_target_stage_that_someone_enter_stage_prompt(self.npc_name, self.stage_name, self.last_stage_name)
        return event    
####################################################################################################################################
####################################################################################################################################
#################################################################################################################################### 
class ObserveOtherNPCAppearanceAfterEnterStageEvent(IDirectorEvent):

    def __init__(self, who_enter_stage: str, enter_stage_name: str, all_appearance_data: Dict[str, str]) -> None:
        self.who_enter_stage = who_enter_stage
        self.enter_stage_name = enter_stage_name
        self.all_appearance_data = all_appearance_data
        #
        self.npc_appearance_in_stage = all_appearance_data.copy()
        self.npc_appearance_in_stage.pop(who_enter_stage)

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who_enter_stage:
            # 已经在场景里的人看到的是进来的人的外貌
            appearance = self.all_appearance_data.get(self.who_enter_stage, "")
            return someone_came_into_my_stage_his_appearance_prompt(self.who_enter_stage, appearance)

        ## 进入场景的人看到的是场景里的人的外貌
        return npc_appearance_in_this_stage_prompt(self.who_enter_stage, self.npc_appearance_in_stage)
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""
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
class NPCLeaveForFailedBecauseNoExitConditionMatch(IDirectorEvent):

    def __init__(self, npcname: str, stagename: str, tips: str, is_prison_break: bool) -> None:
        self.npcname = npcname
        self.stagename = stagename
        self.tips = tips
        self.is_prison_break = is_prison_break

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.npcname:
            # 跟你无关不用关注，原因类的东西，是失败后矫正用，所以只有自己知道即可
            return ""
        no_exit_condition_match_event = leave_for_stage_failed_because_no_exit_condition_match_prompt(self.npcname, self.stagename, self.tips, self.is_prison_break)
        return no_exit_condition_match_event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        if self.is_prison_break:
            #如果是越狱的行动，也让场景知道，提高场景的上下文。
            return leave_for_stage_failed_because_no_exit_condition_match_prompt(self.npcname, self.stagename, self.tips, self.is_prison_break)
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








