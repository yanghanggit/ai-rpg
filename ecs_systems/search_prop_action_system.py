from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from ecs_systems.action_components import (
    SearchPropAction,
    DeadAction,
    CheckStatusAction,
)

from ecs_systems.components import ActorComponent, StageComponent

# from my_agent.agent_action import AgentAction
from loguru import logger
from ecs_systems.stage_director_component import StageDirectorComponent
from typing import List, override
from file_system.files_def import PropFile
from ecs_systems.stage_director_event import IStageDirectorEvent
import ecs_systems.cn_builtin_prompt as builtin_prompt
import file_system.helper


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorSearchPropFailedEvent(IStageDirectorEvent):

    def __init__(self, who: str, target: str) -> None:
        self._who: str = who
        self._target: str = target

    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._who:
            ## 只有自己知道
            return ""
        return builtin_prompt.search_prop_action_failed_prompt(self._who, self._target)

    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return ""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class ActorSearchPropSuccessEvent(IStageDirectorEvent):

    #
    def __init__(self, who: str, target: str, stage_name: str) -> None:
        self._who: str = who
        self._target: str = target
        self._stage_name: str = stage_name

    #
    def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
        if actor_name != self._who:
            ## 只有自己知道
            return ""
        return builtin_prompt.search_prop_action_success_prompt(
            self._who, self._target, self._stage_name
        )

    #
    def to_stage(self, stage_name: str, extended_context: RPGEntitasContext) -> str:
        return builtin_prompt.search_prop_action_success_prompt(
            self._who, self._target, self._stage_name
        )


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class SearchPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext):
        super().__init__(context)
        self._context = context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SearchPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(SearchPropAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            if self.search(entity):
                self.on_success(entity)

    ####################################################################################################################################
    def search(self, entity: Entity) -> bool:

        # 在本场景搜索
        safe_name = self._context.safe_get_entity_name(entity)

        stage_entity = self._context.safe_get_stage_entity(entity)
        if stage_entity is None:
            logger.error(f"{safe_name} not in any stage")
            return False
        ##
        stage_comp = stage_entity.get(StageComponent)
        # 场景有这些道具文件
        prop_files = self._context._file_system.get_files(PropFile, stage_comp.name)
        ###
        search_action = entity.get(SearchPropAction)
        # search_action: AgentAction = search_comp.action
        ###
        #
        search_success_count = 0
        for target_prop_name in search_action.values:
            ## 不在同一个场景就不能被搜寻，这个场景不具备这个道具，就无法搜寻
            if not self.check_stage_has_the_prop(target_prop_name, prop_files):
                StageDirectorComponent.add_event_to_stage_director(
                    self._context,
                    stage_entity,
                    ActorSearchPropFailedEvent(safe_name, target_prop_name),
                )
                logger.debug(
                    f"search failed, {target_prop_name} not in {stage_comp.name}"
                )
                continue
            # 交换文件，即交换道具文件即可
            self.stage_exchanges_prop_to_actor(
                stage_comp.name, search_action.name, target_prop_name
            )
            logger.info(f"search success, {target_prop_name} in {stage_comp.name}")
            StageDirectorComponent.add_event_to_stage_director(
                self._context,
                stage_entity,
                ActorSearchPropSuccessEvent(
                    safe_name, target_prop_name, stage_comp.name
                ),
            )
            search_success_count += 1

        return search_success_count > 0

    ####################################################################################################################################
    def check_stage_has_the_prop(
        self, target_name: str, current_stage_prop_files: List[PropFile]
    ) -> bool:
        for propfile in current_stage_prop_files:
            if propfile._name == target_name:
                return True
        return False

    ####################################################################################################################################
    def stage_exchanges_prop_to_actor(
        self, stage_name: str, actor_name: str, prop_file_name: str
    ) -> None:
        # self._context._file_system.give_prop_file(stage_name, actor_name, prop_file_name)
        file_system.helper.give_prop_file(
            self._context._file_system, stage_name, actor_name, prop_file_name
        )

    ####################################################################################################################################
    def on_success(self, entity: Entity) -> None:
        if entity.has(CheckStatusAction):
            return
        actor_comp = entity.get(ActorComponent)
        entity.add(
            CheckStatusAction,
            actor_comp.name,
            CheckStatusAction.__name__,
            [actor_comp.name],
        )


####################################################################################################################################
