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
###################################################################################################################
    def perception_npcs_in_stage(self, entity: Entity) -> List[str]:
        res: List[str] = []
        safestage = self.context.safe_get_stage_entity(entity)
        if safestage is None:
            return res
        stagecomp: StageComponent = safestage.get(StageComponent)

        file_system = self.context.file_system
        selfname = self.context.safe_get_entity_name(entity)
        npcs = self.context.npcs_in_this_stage(stagecomp.name)
        for npc in npcs:
            if npc == entity:
                #过滤掉自己
                continue
            hisname = self.context.safe_get_entity_name(npc)
            I_known_this_npc = file_system.get_known_npc_file(selfname, hisname)
            if I_known_this_npc is None:
                #过滤掉不认识的NPC
                logger.error(f"{selfname}不认识{hisname}, 无法感知。后续可以加入形象系统")
                continue
            res.append(self.context.safe_get_entity_name(npc))

        return res
###################################################################################################################
    def perception_props_in_stage(self, entity: Entity) -> List[str]:
        res: List[str] = []
        safestage = self.context.safe_get_stage_entity(entity)
        if safestage is None:
            return res
        stagecomp: StageComponent = safestage.get(StageComponent)
        file_system = self.context.file_system
        props_in_stage = file_system.get_prop_files(stagecomp.name)
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
        logger.debug("<<<<<<<<<<<<<  PerceptionActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.perception(entity)
###################################################################################################################
    def perception(self, entity: Entity) -> None:
        safe_npc_name = self.context.safe_get_entity_name(entity)
        logger.debug(f"PerceptionActionSystem: {safe_npc_name} is perceiving")

        #
        helper = PerceptionActionHelper(self.context)
        ## 场景里有哪些人？
        npcs_in_stage = helper.perception_npcs_in_stage(entity)
        ## 场景里有哪些物品？
        props_in_stage = helper.perception_props_in_stage(entity)
        ## 通知导演
        #self.notifydirector(entity, npcs_in_stage, props_in_stage)
        stageentity = self.context.safe_get_stage_entity(entity)
        assert stageentity is not None
        safe_stage_name = self.context.safe_get_entity_name(stageentity)   
        notify_stage_director(self.context, entity, NPCPerceptionEvent(safe_npc_name, safe_stage_name, npcs_in_stage, props_in_stage))
###################################################################################################################
    # def notifydirector(self, entity: Entity, npcs_in_stage: List[str], props_in_stage: List[str]) -> None:
    #     stageentity = self.context.safe_get_stage_entity(entity)
    #     if stageentity is None or not stageentity.has(StageDirectorComponent):
    #         return
    #     safename = self.context.safe_get_entity_name(entity)
    #     if safename == "":
    #         return
    #     directorcomp: StageDirectorComponent = stageentity.get(StageDirectorComponent)
    #     stagename = self.context.safe_get_entity_name(stageentity)
    #     directorcomp.addevent(NPCPerceptionEvent(safename, stagename, npcs_in_stage, props_in_stage))
###################################################################################################################