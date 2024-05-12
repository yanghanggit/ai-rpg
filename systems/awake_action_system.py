# from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
# from auxiliary.components import StageComponent, AwakeActionComponent
# from auxiliary.actor_action import ActorAction
# from auxiliary.extended_context import ExtendedContext
# from loguru import logger
# from auxiliary.director_component import notify_stage_director
# from auxiliary.director_event import IDirectorEvent
# from auxiliary.cn_builtin_prompt import npc_in_the_stage_wakes_up_prompt



# class AwakeEvent(IDirectorEvent):

#     def __init__(self, who_is_waking_up: str, stagename: str, he_remembered_something_when_woke_up: str) -> None:
#         self.who_is_waking_up = who_is_waking_up
#         self.stagename = stagename
#         self.he_remembered_something_when_woke_up = he_remembered_something_when_woke_up
    
#     def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
#         return ""
    
#     def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
#         prompt = npc_in_the_stage_wakes_up_prompt(self.who_is_waking_up, self.stagename, self.he_remembered_something_when_woke_up, extended_context)
#         return prompt
    

# class AwakeActionSystem(ReactiveProcessor):

#     def __init__(self, context: ExtendedContext) -> None:
#         super().__init__(context)
#         self.context = context
# ####################################################################################################
#     def get_trigger(self) -> dict[Matcher, GroupEvent]:
#         return {Matcher(AwakeActionComponent): GroupEvent.ADDED}
# ####################################################################################################
#     def filter(self, entity: Entity) -> bool:
#         return entity.has(AwakeActionComponent)
# ####################################################################################################
#     def react(self, entities: list[Entity]) -> None:
#         for entity in entities:
#             self.awake(entity) 
# ####################################################################################################
#     def awake(self, entity: Entity) -> None:
#         stageentity = self.context.safe_get_stage_entity(entity)
#         if stageentity is None:
#             return
#         #
#         safe_name = self.context.safe_get_entity_name(entity)
#         awakecomp: AwakeActionComponent = entity.get(AwakeActionComponent)
#         stagecomp: StageComponent = stageentity.get(StageComponent)
#         #
#         action: ActorAction = awakecomp.action
#         singlevalue = action.single_value()
#         notify_stage_director(self.context, stageentity, AwakeEvent(safe_name, stagecomp.name, singlevalue))
# ####################################################################################################