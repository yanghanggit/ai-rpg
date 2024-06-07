from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import (  SearchActionComponent, 
                                    NPCComponent,
                                    StageComponent,
                                    DeadActionComponent,
                                    CheckStatusActionComponent)
from auxiliary.actor_action import ActorAction
from loguru import logger
from auxiliary.director_component import notify_stage_director
from typing import List
from auxiliary.file_def import PropFile

from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import search_action_failed_prompt, search_action_success_prompt


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class NPCSearchFailedEvent(IDirectorEvent):

    def __init__(self, who_search_failed: str, target: str) -> None:
        self.who_search_failed = who_search_failed
        self.target = target

    #
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who_search_failed:
            ## 只有自己知道
            return ""
        event = search_action_failed_prompt(self.who_search_failed, self.target)
        return event
    
    #
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = search_action_failed_prompt(self.who_search_failed, self.target)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class NPCSearchSuccessEvent(IDirectorEvent):

    #
    def __init__(self, who_search_success: str, target: str, stagename: str) -> None:
        self.who_search_success = who_search_success
        self.target = target
        self.stagename = stagename

    #
    def tonpc(self, npcname: str, extended_context: ExtendedContext) -> str:
        if npcname != self.who_search_success:
            ## 只有自己知道
            return ""
        event = search_action_success_prompt(self.who_search_success, self.target, self.stagename)
        return event
    
    #
    def tostage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = search_action_success_prompt(self.who_search_success, self.target, self.stagename)
        return event

class SearchActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(SearchActionComponent): GroupEvent.ADDED }
###################################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(SearchActionComponent) and entity.has(NPCComponent) and not entity.has(DeadActionComponent)
###################################################################################################################
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            search_any = self.search(entity)
            if search_any:
                self.after_search_success(entity)
###################################################################################################################
    def search(self, entity: Entity) -> bool:
        # 
        search_any_prop_success = False
        # 在本场景搜索
        file_system = self.context.file_system
        safe_npc_name = self.context.safe_get_entity_name(entity)

        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None:
            logger.error(f"npc {safe_npc_name} not in any stage")
            return search_any_prop_success
        ##
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
                notify_stage_director(self.context, stageentity, NPCSearchFailedEvent(safe_npc_name, targetpropname))
                logger.debug(f"search failed, {targetpropname} not in {stagecomp.name}")
                continue
            # 交换文件，即交换道具文件即可
            self.stage_exchanges_prop_to_npc(stagecomp.name, action.name, targetpropname)
            logger.info(f"search success, {targetpropname} in {stagecomp.name}")
            notify_stage_director(self.context, stageentity, NPCSearchSuccessEvent(safe_npc_name, targetpropname, stagecomp.name))
            search_any_prop_success = True

        return search_any_prop_success
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
    def after_search_success(self, entity: Entity) -> None:
        if entity.has(CheckStatusActionComponent):
            return
        npccomp: NPCComponent = entity.get(NPCComponent)
        action = ActorAction(npccomp.name, CheckStatusActionComponent.__name__, [npccomp.name])
        entity.add(CheckStatusActionComponent, action)
###################################################################################################################
