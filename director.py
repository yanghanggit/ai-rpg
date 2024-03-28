
from auxiliary.extended_context import ExtendedContext
from typing import List
from auxiliary.prompt_maker import broadcast_action_prompt, speak_action_prompt, __unique_prop_taken_away__, kill_someone, attack_someone
from loguru import logger
from auxiliary.print_in_color import Color

"""
directorscripts
"""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class DirectorEvent:
    ### 这一步处理可以达到每个人看到的事件有不同的陈述，而不是全局唯一的陈述
    def convert(self, targetname: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class BroadcastEvent(DirectorEvent):
    def __init__(self, whobroadcast: str, stagename: str, content: str) -> None:
        self.whobroadcast = whobroadcast
        self.stagename = stagename
        self.content = content

    def __str__(self) -> str:
        return f"BroadcastEvent({self.whobroadcast}, {self.stagename}, {self.content})"
    
    def convert(self, targetname: str, extended_context: ExtendedContext) -> str:
        if targetname != self.whobroadcast:
            logger.error(f"广播者与收听者不是一个人 => {targetname} vs {self.whobroadcast}")

        broadcastcontent = broadcast_action_prompt(self.whobroadcast, self.stagename, self.content, extended_context)
        logger.info(f"{Color.HEADER}{broadcastcontent}{Color.ENDC}")
        
        return broadcastcontent
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class SpeakEvent(DirectorEvent):
    def __init__(self, whospeak: str, target: str, message: str) -> None:
        self.whospeak = whospeak
        self.target = target
        self.message = message

    def __str__(self) -> str:
        return f"SpeakEvent({self.whospeak}, {self.target}, {self.message})"

    def convert(self, targetname: str, extended_context: ExtendedContext) -> str:
        if targetname != self.whospeak:
            logger.error(f"说话者与收听者不是一个人 => {targetname} vs {self.whospeak}")

        speakcontent: str = speak_action_prompt(self.whospeak, self.target, self.message, extended_context)
        logger.info(f"{Color.HEADER}{speakcontent}{Color.ENDC}")

        return speakcontent
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class SearchFailedEvent(DirectorEvent):
    def __init__(self, who_search_failed: str, target: str) -> None:
        self.who_search_failed = who_search_failed
        self.target = target

    def __str__(self) -> str:
        return f"SearchFailedEvent({self.who_search_failed}, {self.target})"

    def convert(self, targetname: str, extended_context: ExtendedContext) -> str:
        if targetname != self.who_search_failed:
            logger.error(f"搜索失败的人与收听者不是一个人 => {targetname} vs {self.who_search_failed}")
        event = __unique_prop_taken_away__(self.who_search_failed, self.target)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class KillSomeoneEvent(DirectorEvent):
    def __init__(self, attacker: str, target: str) -> None:
        self.attacker = attacker
        self.target = target

    def __str__(self) -> str:
        return f"KillSomeoneEvent({self.attacker}, {self.target})"
    
    def convert(self, targetname: str, extended_context: ExtendedContext) -> str:
        if targetname != self.attacker:
            logger.error(f"杀人者与收听者不是一个人 => {targetname} vs {self.attacker}")

        event = kill_someone(self.attacker, self.target)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class AttackSomeoneEvent(DirectorEvent):
    def __init__(self, attacker: str, target: str, damage: int, curhp: int, maxhp: int) -> None:
        self.attacker = attacker
        self.target = target
        self.damage = damage
        self.curhp = curhp
        self.maxhp = maxhp

    def __str__(self) -> str:
        return "AttackSomeoneEvent"

    def convert(self, targetname: str, extended_context: ExtendedContext) -> str:
        if targetname != self.attacker:
            logger.error(f"攻击者与收听者不是一个人 => {targetname} vs {self.attacker}")

        event = attack_someone(self.attacker, self.target, self.damage, self.curhp, self.maxhp)
        logger.info(event)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class Director:

    def __init__(self, name: str) -> None:
        self.name = name
        self.events: list[DirectorEvent] = []

    def addevent(self, event: DirectorEvent) -> None:
        self.events.append(event)

    def convert(self, targetname: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self.events:
            batch.append(event.convert(targetname, extended_context))
        return batch

    def clear(self) -> None:
        self.events.clear()
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################