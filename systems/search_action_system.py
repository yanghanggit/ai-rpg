from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  SearchActionComponent, 
                                    NPCComponent,
                                    StageComponent)
from auxiliary.actor_action import ActorAction
from loguru import logger
from auxiliary.director_component import DirectorComponent
from auxiliary.director_event import NPCSearchFailedEvent, NPCSearchSuccessEvent
from typing import List
from auxiliary.file_def import PropFile

class SearchActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(SearchActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(SearchActionComponent) and entity.has(NPCComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  SearchPropsSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.search(entity)
###################################################################################################################
    def search(self, entity: Entity) -> None:
        # 在本场景搜索
        file_system = self.context.file_system

        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None:
            return
        stagecomp: StageComponent = stageentity.get(StageComponent)

        # 场景有这些道具文件
        propfiles = file_system.get_prop_files(stagecomp.name)
        ###
        searchactioncomp: SearchActionComponent = entity.get(SearchActionComponent)
        action: ActorAction = searchactioncomp.action
        searchtargets: set[str] = set(action.values)
        ###
        for targetpropname in searchtargets:
            ## 不在同一个场景就不能被搜寻，这个场景不具备这个道具，就无法搜寻
            if not self.check_stage_has_the_prop(targetpropname, propfiles):
                self.notify_director_search_failed(entity, targetpropname)
                logger.debug(f"search failed, {targetpropname} not in {stagecomp.name}")
                continue
            # 交换文件，即交换道具文件即可
            self.stage_exchanges_prop_to_npc(stagecomp.name, action.name, targetpropname)
            logger.debug(f"search success, {targetpropname} in {stagecomp.name}")
            self.notify_director_search_success(entity, targetpropname)
###################################################################################################################
    def check_stage_has_the_prop(self, targetname: str, curstagepropfiles: List[PropFile]) -> bool:
        for propfile in curstagepropfiles:
            if propfile.name == targetname:
                return True
        return False
###################################################################################################################
    def stage_exchanges_prop_to_npc(self, stagename: str, npcname: str, propfilename: str) -> None:
        filesystem = self.context.file_system
        filesystem.exchange_prop_file(stagename, npcname, propfilename)
###################################################################################################################
    def notify_director_search_failed(self, entity: Entity, propname: str) -> None:
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        safename = self.context.safe_get_entity_name(entity)
        if safename == "":
            return
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        searchfailedevent = NPCSearchFailedEvent(safename, propname)
        directorcomp.addevent(searchfailedevent)
###################################################################################################################
    def notify_director_search_success(self, entity: Entity, propname: str) -> None:
        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None or not stageentity.has(DirectorComponent):
            return
        safe_npc_name = self.context.safe_get_entity_name(entity)
        if safe_npc_name == "":
            return
        directorcomp: DirectorComponent = stageentity.get(DirectorComponent)
        safe_stage_name = self.context.safe_get_entity_name(stageentity)
        search_success_event = NPCSearchSuccessEvent(safe_npc_name, propname, safe_stage_name)
        directorcomp.addevent(search_success_event)
###################################################################################################################