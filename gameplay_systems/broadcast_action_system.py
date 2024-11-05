from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import final, override
from my_components.components import StageComponent
from my_components.action_components import BroadcastAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
import gameplay_systems.builtin_prompt_util as builtin_prompt_util
from my_models.event_models import AgentEvent


def _generate_broadcast_prompt(src_name: str, dest_name: str, content: str) -> str:
    return f"# {builtin_prompt_util.ConstantPromptTag.BROADCASE_ACTION_TAG} {src_name}对{dest_name}里的所有人说:{content}"


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
            self.handle(entity)

    ####################################################################################################
    ## 目前的设定是场景与Actor都能广播，后续会调整与修改。
    def handle(self, entity: Entity) -> None:
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        if current_stage_entity is None:
            return

        broadcast_action = entity.get(BroadcastAction)
        self._context.broadcast_event_in_stage(
            current_stage_entity,
            AgentEvent(
                message_content=_generate_broadcast_prompt(
                    broadcast_action.name,
                    current_stage_entity.get(StageComponent).name,
                    " ".join(broadcast_action.values),
                )
            ),
        )

    ####################################################################################################
