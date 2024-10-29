from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.action_components import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
import gameplay_systems.action_helper
from rpg_game.rpg_game import RPGGame


@final
class PostActionSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        all_actions_register = (
            ACTOR_AVAILABLE_ACTIONS_REGISTER | STAGE_AVAILABLE_ACTIONS_REGISTER
        )

        gameplay_systems.action_helper.remove_actions(
            self._context, all_actions_register
        )
        self.test()

    ############################################################################################################
    def test(self) -> None:
        stage_entities = self._context.get_group(
            Matcher(any_of=STAGE_AVAILABLE_ACTIONS_REGISTER)
        ).entities
        assert (
            len(stage_entities) == 0
        ), f"Stage entities with actions: {stage_entities}"
        actor_entities = self._context.get_group(
            Matcher(any_of=ACTOR_AVAILABLE_ACTIONS_REGISTER)
        ).entities
        assert (
            len(actor_entities) == 0
        ), f"Actor entities with actions: {actor_entities}"


############################################################################################################
