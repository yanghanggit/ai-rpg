from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import Any, Final, FrozenSet, NamedTuple, Set, final, override
from game.tcg_game import TCGGame
from components.registry import ACTIONS_REGISTRY_2


@final
class PostDungeonStateSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    def execute(self) -> None:

        actions_set: Final[FrozenSet[type[NamedTuple]]] = frozenset(
            ACTIONS_REGISTRY_2.values()
        )

        self._clear_actions(actions_set)
        self._test(actions_set)

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
    def _test(self, registered_actions: FrozenSet[type[NamedTuple]]) -> None:
        entities = self._game.get_group(Matcher(any_of=registered_actions)).entities
        assert len(entities) == 0, f"entities with actions: {entities}"

    ############################################################################################################
