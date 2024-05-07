from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (CheckStatusActionComponent)
from loguru import logger
from auxiliary.director_component import notify_stage_director
from auxiliary.director_event import NPCCheckStatusEvent
from typing import List


class CheckStatusActionHelper:
    def __init__(self, context: ExtendedContext):
        self.context = context
        self.propnames: List[str] = []
        self.prop_and_desc: List[str] = []

    def clear(self) -> None:
        self.propnames.clear()
        self.prop_and_desc.clear()

    def handle(self, entity: Entity) -> None:
        # 先清空
        self.clear()
        # 再检查
        safename = self.context.safe_get_entity_name(entity)
        logger.debug(f"{safename} is checking status")
        filesystem = self.context.file_system
        props = filesystem.get_prop_files(safename)
        for prop in props:
            self.propnames.append(prop.name)
            self.prop_and_desc.append(f"{prop.name}:{prop.prop.description}")
###################################################################################################################       




class CheckStatusActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(CheckStatusActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(CheckStatusActionComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  CheckStatusActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.check_status(entity)
###################################################################################################################
    # 临时写成这样，就是检查自己有哪些道具
    def check_status(self, entity: Entity) -> None:
        safe_npc_name = self.context.safe_get_entity_name(entity)
        logger.debug(f"{safe_npc_name} is checking status")
        #
        helper = CheckStatusActionHelper(self.context)
        helper.handle(entity)
        propnames = helper.propnames
        prop_and_desc = helper.prop_and_desc

        #
        notify_stage_director(self.context, entity, NPCCheckStatusEvent(safe_npc_name, propnames, prop_and_desc))
        #
        #self.notifydirector(entity, propnames, prop_and_desc)
####################################################################################################
    # def notifydirector(self, entity: Entity, propnames: List[str], prop_and_desc: List[str]) -> None:
    #     stageentity = self.context.safe_get_stage_entity(entity)
    #     if stageentity is None or not stageentity.has(StageDirectorComponent):
    #         return
    #     safename = self.context.safe_get_entity_name(entity)
    #     if safename == "":
    #         return
    #     directorcomp: StageDirectorComponent = stageentity.get(StageDirectorComponent)
    #     directorcomp.addevent(NPCCheckStatusEvent(safename, propnames, prop_and_desc))
###################################################################################################################
    