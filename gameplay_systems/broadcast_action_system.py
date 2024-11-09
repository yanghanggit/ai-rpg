from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import final, override
from my_components.action_components import BroadcastAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from my_models.event_models import BroadcastEvent


def _generate_broadcast_prompt(actor_name: str, stage_name: str, content: str) -> str:
    return f"# 发生事件: {actor_name} 对 {stage_name} 里的所有人说: {content}"


####################################################################################################
####################################################################################################
####################################################################################################


@final
class BroadcastActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(BroadcastAction): GroupEvent.ADDED}

    ####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(BroadcastAction)

    ####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_broadcast_action(entity)

    ####################################################################################################
    def _process_broadcast_action(self, entity: Entity) -> None:
        stage_entity = self._context.safe_get_stage_entity(entity)
        if stage_entity is None:
            return

        broadcast_action = entity.get(BroadcastAction)
        stage_name = self._context.safe_get_entity_name(stage_entity)
        content = " ".join(broadcast_action.values)
        self._context.broadcast_event_in_stage(
            stage_entity,
            BroadcastEvent(
                message=_generate_broadcast_prompt(
                    broadcast_action.name,
                    stage_name,
                    content,
                ),
                actor_name=broadcast_action.name,
                stage_name=stage_name,
                content=content,
            ),
        )

    ####################################################################################################
