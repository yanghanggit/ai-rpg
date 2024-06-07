from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  TradeActionComponent,CheckStatusActionComponent, DeadActionComponent,
                                    ActorComponent)
from loguru import logger
from auxiliary.actor_plan_and_action import ActorAction
from auxiliary.target_and_message_format_handle import conversation_check, parse_target_and_message, ErrorConversationEnable
from typing import Optional, List
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import trade_action_prompt


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class NPCTradeEvent(IDirectorEvent):

    def __init__(self, fromwho: str, towho: str, propname: str, traderes: bool) -> None:
        self.fromwho = fromwho
        self.towho = towho
        self.propname = propname
        self.traderes = traderes

    def to_actor(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.fromwho or npcname != self.towho:
            return ""
        
        tradecontent = trade_action_prompt(self.fromwho, self.towho, self.propname, self.traderes)
        return tradecontent
    
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        return ""

class TradeActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(TradeActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(TradeActionComponent) and entity.has(ActorComponent)  and not entity.has(DeadActionComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            trade_success_target_names = self.trade(entity)
            for name in trade_success_target_names:
                pass #todo 可以不用？这样更好玩？比如你收到谁谁谁给了你啥，你需要自己自检一下看看是啥？
                #self.after_trade_success(name)
###################################################################################################################
    def trade(self, entity: Entity) -> List[str]:

        trade_success_target_names: List[str] = []
        safe_npc_name = self.context.safe_get_entity_name(entity)
        logger.debug(f"TradeActionSystem: {safe_npc_name} is trading")

        tradecomp: TradeActionComponent = entity.get(TradeActionComponent)
        tradeaction: ActorAction = tradecomp.action
        for value in tradeaction.values:

            parse = parse_target_and_message(value)
            targetname: Optional[str] = parse[0]
            message: Optional[str] = parse[1]
            
            if targetname is None or message is None:
                # 不能交谈就是不能交换道具
                continue
    
            if conversation_check(self.context, entity, targetname) != ErrorConversationEnable.VALID:
                # 不能交谈就是不能交换道具
                continue
            ##
            propname = message
            traderes = self._trade_(entity, targetname, propname)
            notify_stage_director(self.context, entity, NPCTradeEvent(safe_npc_name, targetname, propname, traderes))
            trade_success_target_names.append(targetname)

        return trade_success_target_names
###################################################################################################################
    def _trade_(self, entity: Entity, target_npc_name: str, mypropname: str) -> bool:
        filesystem = self.context.file_system
        safename = self.context.safe_get_entity_name(entity)
        myprop = filesystem.get_prop_file(safename, mypropname)
        if myprop is None:
            return False
        filesystem.exchange_prop_file(safename, target_npc_name, mypropname)
        return True
###################################################################################################################
    def after_trade_success(self, name: str) -> None:
        entity = self.context.getnpc(name)
        if entity is None:
            logger.error(f"npc {name} not found")
            return
        if entity.has(CheckStatusActionComponent):
            return
        npccomp: ActorComponent = entity.get(ActorComponent)
        action = ActorAction(npccomp.name, CheckStatusActionComponent.__name__, [npccomp.name])
        entity.add(CheckStatusActionComponent, action)
###################################################################################################################