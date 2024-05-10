from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  PerceptionActionComponent,
                                    StageComponent,
                                    NPCComponent)
from loguru import logger
from typing import List
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import NPCPerceptionEvent



class PerceptionActionHelper:

    def __init__(self, context: ExtendedContext):
        self.context = context
        self.npcs_in_stage: List[str] = []
        self.props_in_stage: List[str] = []
###################################################################################################################
    def perception(self, entity: Entity) -> None:
        safestage = self.context.safe_get_stage_entity(entity)
        if safestage is None:
            logger.error(f"PerceptionActionHelper: {self.context.safe_get_entity_name(entity)} can't find the stage")
            return
        self.npcs_in_stage = self.perception_npcs_in_stage(entity, safestage)
        self.props_in_stage = self.perception_props_in_stage(entity, safestage)
###################################################################################################################
    def perception_npcs_in_stage(self, entity: Entity, stageentity: Entity) -> List[str]:
        res: List[str] = []
        stagecomp: StageComponent = stageentity.get(StageComponent)
        npcs = self.context.npcs_in_this_stage(stagecomp.name)
        for npc in npcs:
            if npc == entity:
                #过滤掉自己
                continue
            res.append(self.context.safe_get_entity_name(npc))
        return res
###################################################################################################################
    def perception_props_in_stage(self, entity: Entity, stageentity: Entity) -> List[str]:
        res: List[str] = []
        stagecomp: StageComponent = stageentity.get(StageComponent)
        props_in_stage = self.context.file_system.get_prop_files(stagecomp.name)
        for prop in props_in_stage:
            res.append(prop.name)
        return res
###################################################################################################################



class PerceptionActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(PerceptionActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(PerceptionActionComponent) and entity.has(NPCComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.perception(entity)
###################################################################################################################
    def perception(self, entity: Entity) -> None:
        safe_npc_name = self.context.safe_get_entity_name(entity)
        logger.debug(f"PerceptionActionSystem: {safe_npc_name} is perceiving")
        #
        helper = PerceptionActionHelper(self.context)
        helper.perception(entity)
        #
        stageentity = self.context.safe_get_stage_entity(entity)
        assert stageentity is not None
        safe_stage_name = self.context.safe_get_entity_name(stageentity)   
        notify_stage_director(self.context, entity, NPCPerceptionEvent(safe_npc_name, safe_stage_name, helper.npcs_in_stage, helper.props_in_stage))
###################################################################################################################
