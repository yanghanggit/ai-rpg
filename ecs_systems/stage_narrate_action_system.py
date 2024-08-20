from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import override
from ecs_systems.action_components import StageNarrateAction
from ecs_systems.components import StageNarrateComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_agent.agent_action import AgentAction


############################################################################################################
class StageNarrateActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context = context

    ############################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StageNarrateAction): GroupEvent.ADDED}

    ############################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StageNarrateAction) and entity.has(StageNarrateComponent)

    ############################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ############################################################################################################
    def handle(self, stage_entity: Entity) -> None:
        action: AgentAction = stage_entity.get(StageNarrateAction).action
        stage_narrate_content = " ".join(action._values)
        #action.join_values()
        if stage_narrate_content == "":
            return

        stage_narrate_comp = stage_entity.get(StageNarrateComponent)
        stage_entity.replace(
            StageNarrateComponent,
            stage_narrate_comp.name,
            stage_narrate_content,
            self._context._execute_count,
        )

    ############################################################################################################
