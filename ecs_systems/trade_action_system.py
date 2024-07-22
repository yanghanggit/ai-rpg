from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from ecs_systems.action_components import (TradeActionComponent,CheckStatusActionComponent, DeadActionComponent)
from ecs_systems.components import ActorComponent
from loguru import logger
from my_agent.agent_action import AgentAction
from gameplay_checks.conversation_check import conversation_check, ErrorConversationEnable
from typing import List, override
from ecs_systems.stage_director_component import notify_stage_director
from ecs_systems.stage_director_event import IStageDirectorEvent
from builtin_prompt.cn_builtin_prompt import trade_action_prompt


class ActorTradeEvent(IStageDirectorEvent):

    def __init__(self, from_who: str, to_who: str, prop_name: str, trade_result: bool) -> None:
        self._from_who: str = from_who
        self._to_who: str = to_who
        self._prop_name: str = prop_name
        self._trade_result: bool = trade_result

    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self._from_who or actor_name != self._to_who:
            return ""
        return trade_action_prompt(self._from_who, self._to_who, self._prop_name, self._trade_result)
    
    def to_stage(self, stage_name: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class TradeActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self._context = context
####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(TradeActionComponent): GroupEvent.ADDED }
####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TradeActionComponent) and entity.has(ActorComponent)  and not entity.has(DeadActionComponent)
####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.trade(entity)
####################################################################################################################################
    def trade(self, entity: Entity) -> List[str]:

        trade_success_target_names: List[str] = []
        safe_name = self._context.safe_get_entity_name(entity)
        logger.debug(f"TradeActionSystem: {safe_name} is trading")

        trade_comp: TradeActionComponent = entity.get(TradeActionComponent)
        trade_action: AgentAction = trade_comp.action
        target_and_message = trade_action.target_and_message_values()
        for tp in target_and_message:
            targetname = tp[0]
            message = tp[1]

            if conversation_check(self._context, entity, targetname) != ErrorConversationEnable.VALID:
                # 不能交谈就是不能交换道具
                continue
    
            propname = message
            traderes = self._trade_(entity, targetname, propname)
            notify_stage_director(self._context, entity, ActorTradeEvent(safe_name, targetname, propname, traderes))
            trade_success_target_names.append(targetname)

        return trade_success_target_names
####################################################################################################################################
    def _trade_(self, entity: Entity, target_actor_name: str, mypropname: str) -> bool:
        filesystem = self._context._file_system
        safename = self._context.safe_get_entity_name(entity)
        myprop = filesystem.get_prop_file(safename, mypropname)
        if myprop is None:
            return False
        filesystem.exchange_prop_file(safename, target_actor_name, mypropname)
        return True
####################################################################################################################################
    def after_trade_success(self, name: str) -> None:
        entity = self._context.get_actor_entity(name)
        if entity is None:
            logger.error(f"actor {name} not found")
            return
        if entity.has(CheckStatusActionComponent):
            return
        actor_comp = entity.get(ActorComponent)
        entity.add(CheckStatusActionComponent, AgentAction(actor_comp.name, CheckStatusActionComponent.__name__, [actor_comp.name]))
####################################################################################################################################