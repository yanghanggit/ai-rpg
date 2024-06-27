from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from auxiliary.components import (  SearchActionComponent, 
                                    ActorComponent,
                                    StageComponent,
                                    DeadActionComponent,
                                    CheckStatusActionComponent)
from auxiliary.actor_plan_and_action import ActorAction
from loguru import logger
from auxiliary.director_component import notify_stage_director
from typing import List, override, Set
from file_system.files_def import PropFile

from auxiliary.director_event import IDirectorEvent
from builtin_prompt.cn_builtin_prompt import search_action_failed_prompt, search_action_success_prompt


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class ActorSearchFailedEvent(IDirectorEvent):

    def __init__(self, who_search_failed: str, target: str) -> None:
        self.who_search_failed = who_search_failed
        self.target = target

    #
    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.who_search_failed:
            ## 只有自己知道
            return ""
        event = search_action_failed_prompt(self.who_search_failed, self.target)
        return event
    
    #
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = search_action_failed_prompt(self.who_search_failed, self.target)
        return event
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################     
class ActorSearchSuccessEvent(IDirectorEvent):

    #
    def __init__(self, who_search_success: str, target: str, stagename: str) -> None:
        self.who_search_success = who_search_success
        self.target = target
        self.stagename = stagename

    #
    def to_actor(self, actor_name: str, extended_context: ExtendedContext) -> str:
        if actor_name != self.who_search_success:
            ## 只有自己知道
            return ""
        event = search_action_success_prompt(self.who_search_success, self.target, self.stagename)
        return event
    
    #
    def to_stage(self, stagename: str, extended_context: ExtendedContext) -> str:
        event = search_action_success_prompt(self.who_search_success, self.target, self.stagename)
        return event

class SearchActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext):
        super().__init__(context)
        self.context = context
###################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return { Matcher(SearchActionComponent): GroupEvent.ADDED }
###################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SearchActionComponent) and entity.has(ActorComponent) and not entity.has(DeadActionComponent)
###################################################################################################################
    @override
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
        safe_name = self.context.safe_get_entity_name(entity)

        stageentity = self.context.safe_get_stage_entity(entity)
        if stageentity is None:
            logger.error(f"{safe_name} not in any stage")
            return search_any_prop_success
        ##
        stagecomp: StageComponent = stageentity.get(StageComponent)
        # 场景有这些道具文件
        propfiles = file_system.get_prop_files(stagecomp.name)
        ###
        searchactioncomp: SearchActionComponent = entity.get(SearchActionComponent)
        action: ActorAction = searchactioncomp.action
        searchtargets: Set[str] = set(action.values)
        ###
        for targetpropname in searchtargets:
            ## 不在同一个场景就不能被搜寻，这个场景不具备这个道具，就无法搜寻
            if not self.check_stage_has_the_prop(targetpropname, propfiles):
                notify_stage_director(self.context, stageentity, ActorSearchFailedEvent(safe_name, targetpropname))
                logger.debug(f"search failed, {targetpropname} not in {stagecomp.name}")
                continue
            # 交换文件，即交换道具文件即可
            self.stage_exchanges_prop_to_actor(stagecomp.name, action.name, targetpropname)
            logger.info(f"search success, {targetpropname} in {stagecomp.name}")
            notify_stage_director(self.context, stageentity, ActorSearchSuccessEvent(safe_name, targetpropname, stagecomp.name))
            search_any_prop_success = True

        return search_any_prop_success
###################################################################################################################
    def check_stage_has_the_prop(self, targetname: str, curstagepropfiles: List[PropFile]) -> bool:
        for propfile in curstagepropfiles:
            if propfile._name == targetname:
                return True
        return False
###################################################################################################################
    def stage_exchanges_prop_to_actor(self, stagename: str, actor_name: str, propfilename: str) -> None:
        filesystem = self.context.file_system
        filesystem.exchange_prop_file(stagename, actor_name, propfilename)
###################################################################################################################
    def after_search_success(self, entity: Entity) -> None:
        if entity.has(CheckStatusActionComponent):
            return
        actor_comp: ActorComponent = entity.get(ActorComponent)
        action = ActorAction(actor_comp.name, CheckStatusActionComponent.__name__, [actor_comp.name])
        entity.add(CheckStatusActionComponent, action)
###################################################################################################################
