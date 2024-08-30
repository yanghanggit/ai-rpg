from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import override, cast, List
from gameplay_systems.action_components import StageDestoryPropAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from file_system.files_def import PropFile
import gameplay_systems.cn_builtin_prompt as builtin_prompt


############################################################################################################
class StageDestoryPropActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StageDestoryPropAction): GroupEvent.ADDED}

    ############################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StageDestoryPropAction)

    ############################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ############################################################################################################
    def handle(self, stage_entity: Entity) -> None:
        stage_destory_prop_action = stage_entity.get(StageDestoryPropAction)
        if len(stage_destory_prop_action.values) == 0:
            return

        for prop_name in cast(List[str], stage_destory_prop_action.values):

            stage_prop_file = self._context._file_system.get_file(
                PropFile, stage_destory_prop_action.name, prop_name
            )
            if stage_prop_file is None:
                self._context.add_agent_context_message(
                    set({stage_entity}),
                    builtin_prompt.make_stage_prop_lost_prompt(
                        stage_destory_prop_action.name, prop_name
                    ),
                )
                continue

            self._context._file_system.remove_file(stage_prop_file)

            self._context.add_agent_context_message(
                set({stage_entity}),
                builtin_prompt.make_stage_prop_destory_prompt(
                    stage_destory_prop_action.name, prop_name
                ),
            )

    ############################################################################################################
