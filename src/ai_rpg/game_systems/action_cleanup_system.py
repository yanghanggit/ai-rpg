from typing import Final, FrozenSet, final, override
from ..entitas import ExecuteProcessor, Matcher
from ..entitas.components import Component
from ..game.tcg_game import TCGGame
from ..models import (
    ACTION_COMPONENTS_REGISTRY,
    COMPONENTS_REGISTRY,
)
from loguru import logger


@final
class ActionCleanupSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    async def execute(self) -> None:
        actions_set: Final[FrozenSet[type[Component]]] = frozenset(
            ACTION_COMPONENTS_REGISTRY.values()
        )
        self._clear_actions(actions_set)
        self._test(actions_set)

    ############################################################################################################
    def _clear_actions(self, registered_actions: FrozenSet[type[Component]]) -> None:
        entities = self._game.get_group(
            Matcher(any_of=registered_actions)
        ).entities.copy()
        for entity in entities:

            for action_class in registered_actions:

                if entity.has(action_class):

                    # logger.debug(
                    #     f" 清理动作: {action_class} from entity: {entity._name}"
                    # )

                    action = entity.get(action_class)
                    assert action is not None, "动作组件不可能为空"
                    # logger.debug(
                    #     f"清理动作: {action_class} from entity: {entity._name}:\n{action.model_dump_json(indent=2)}"
                    # )

                    entity.remove(action_class)

    ############################################################################################################
    def _test(self, registered_actions: FrozenSet[type[Component]]) -> None:

        # 动作必须被清理掉。
        entities1 = self._game.get_group(Matcher(any_of=registered_actions)).entities
        assert len(entities1) == 0, f"entities with actions: {entities1}"

        # 动作必须在组件注册表中。
        for action_class in ACTION_COMPONENTS_REGISTRY:
            assert (
                action_class in COMPONENTS_REGISTRY
            ), f"{action_class} not in COMPONENTS_REGISTRY"


############################################################################################################
