from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from components.actions import (
    STAGE_AVAILABLE_ACTIONS_REGISTER,
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
)
from typing import final, override, FrozenSet, NamedTuple
from game.tcg_game import TCGGame


@final
class PostActionSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._clear_actions(
            (ACTOR_AVAILABLE_ACTIONS_REGISTER | STAGE_AVAILABLE_ACTIONS_REGISTER)
        )
        self._test()

    ############################################################################################################
    def _clear_actions(self, registered_actions: FrozenSet[type[NamedTuple]]) -> None:
        entities = self._game.get_group(
            Matcher(any_of=registered_actions)
        ).entities.copy()
        for entity in entities:
            for action_class in registered_actions:
                if entity.has(action_class):
                    entity.remove(action_class)

    ############################################################################################################
    def _test(self) -> None:
        stage_entities = self._game.get_group(
            Matcher(any_of=STAGE_AVAILABLE_ACTIONS_REGISTER)
        ).entities
        assert (
            len(stage_entities) == 0
        ), f"Stage entities with actions: {stage_entities}"
        actor_entities = self._game.get_group(
            Matcher(any_of=ACTOR_AVAILABLE_ACTIONS_REGISTER)
        ).entities
        assert (
            len(actor_entities) == 0
        ), f"Actor entities with actions: {actor_entities}"


############################################################################################################
