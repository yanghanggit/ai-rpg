from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from gameplay_systems.action_components import FeedbackAction
from gameplay_systems.components import ActorComponent, StageComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override
from loguru import logger


class FeedbackActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(FeedbackAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(FeedbackAction) and (
            entity.has(ActorComponent) or entity.has(StageComponent)
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:

        feedback_action = entity.get(FeedbackAction)
        assert feedback_action is not None
        logger.debug(f"{"\n".join(feedback_action.values)}")

    ######################################################################################################################################################
