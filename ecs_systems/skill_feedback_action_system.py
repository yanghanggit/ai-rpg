from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
from ecs_systems.action_components import SkillFeedbackAction
from ecs_systems.components import ActorComponent, StageComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import override
from loguru import logger


class SkillFeedbackActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context

    ######################################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SkillFeedbackAction): GroupEvent.ADDED}

    ######################################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SkillFeedbackAction) and (
            entity.has(ActorComponent) or entity.has(StageComponent)
        )

    ######################################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ######################################################################################################################################################
    def handle(self, entity: Entity) -> None:
        logger.debug(f"SkillFeedbackActionSystem: handle: {entity}")
        pass

    ######################################################################################################################################################
