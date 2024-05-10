from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  TradeActionComponent,
                                    NPCComponent)
from loguru import logger
from auxiliary.actor_action import ActorAction
from auxiliary.dialogue_rule import dialogue_enable, parse_target_and_message, ErrorDialogueEnable
from typing import Optional
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import NPCTradeEvent


class TradeActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(TradeActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(TradeActionComponent) and entity.has(NPCComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.trade(entity)
###################################################################################################################
    def trade(self, entity: Entity) -> None:
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
    
            if dialogue_enable(self.context, entity, targetname) != ErrorDialogueEnable.VALID:
                # 不能交谈就是不能交换道具
                continue
            ##
            propname = message
            traderes = self._trade_(entity, targetname, propname)
            notify_stage_director(self.context, entity, NPCTradeEvent(safe_npc_name, targetname, propname, traderes))
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