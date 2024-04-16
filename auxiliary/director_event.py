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
from auxiliary.prompt_maker import whisper_action_prompt

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
        event = __unique_prop_taken_away__(self.who_search_failed, self.target)
        return event
    
    #
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = __unique_prop_taken_away__(self.who_search_failed, self.target)
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
        event = attack_someone(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = attack_someone(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
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
        event = npc_leave_for_stage(self.npc_name, self.current_stage_name, self.leave_for_stage_name)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = npc_leave_for_stage(self.npc_name, self.current_stage_name, self.leave_for_stage_name)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCEnterStageEvent(IDirectorEvent):

    def __init__(self, npc_name: str, stage_name: str) -> None:
        self.npc_name = npc_name
        self.stage_name = stage_name

    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        event = npc_enter_stage(self.npc_name, self.stage_name)
        return event
    
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = npc_enter_stage(self.npc_name, self.stage_name)
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