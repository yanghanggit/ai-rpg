from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (CheckStatusActionComponent)
from loguru import logger
from auxiliary.director_component import DirectorComponent
from auxiliary.director_event import NPCCheckStatusEvent
from typing import List

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
        safename = self.context.safe_get_entity_name(entity)
        logger.debug(f"{safename} is checking status")
        filesystem = self.context.file_system

        props = filesystem.get_prop_files(safename)
        if len(props) == 0:
            return
        
        ## 后续可以优化掉，这个是多余的
        propnames: List[str] = []
        for prop in props:
            propnames.append(prop.name)

        ## 关键
        prop_and_desc: List[str] = []
        for prop in props:
            prop_and_desc.append(f"{prop.name}:{prop.prop.description}")
        
        self.notifydirector(entity, propnames, prop_and_desc)
####################################################################################################
    def notifydirector(self, entity: Entity, propnames: List[str], prop_and_desc: List[str]) -> None:
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        safename = self.context.safe_get_entity_name(entity)
        if safename == "":
            return
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        directorcomp.addevent(NPCCheckStatusEvent(safename, propnames, prop_and_desc))
###################################################################################################################
    