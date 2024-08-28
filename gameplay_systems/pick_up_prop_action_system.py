from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.action_components import (
    PickUpPropAction,
    DeadAction,
    CheckStatusAction,
)
from gameplay_systems.components import ActorComponent, StageComponent
from loguru import logger
from typing import List, override
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt
import file_system.helper
from rpg_game.rpg_game import RPGGame


class PickUpPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PickUpPropAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PickUpPropAction)
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
        search_action = entity.get(PickUpPropAction)
        # search_action: AgentAction = search_comp.action
        ###
        #
        search_success_count = 0
        for target_prop_name in search_action.values:
            ## 不在同一个场景就不能被搜寻，这个场景不具备这个道具，就无法搜寻
            if not self.check_stage_has_the_prop(target_prop_name, prop_files):
                self._context.add_agent_context_message(
                    set({entity}),
                    builtin_prompt.make_search_prop_action_failed_prompt(
                        safe_name, target_prop_name
                    ),
                )

                continue
            # 交换文件，即交换道具文件即可
            self.stage_exchanges_prop_to_actor(
                stage_comp.name, search_action.name, target_prop_name
            )
            logger.info(f"search success, {target_prop_name} in {stage_comp.name}")

            self._context.add_agent_context_message(
                set({entity}),
                builtin_prompt.make_search_prop_action_success_prompt(
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
