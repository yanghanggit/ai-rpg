"""每帧结束时清理所有动作组件，防止动作跨帧残留。"""

from typing import Final, FrozenSet, Mapping, Type, final, override
from ..entitas import ExecuteProcessor, Matcher
from ..entitas.components import Component
from ..game.rpg_game import RPGGame
from ..models import (
    ACTION_COMPONENT_TYPES,
)


@final
class ActionCleanupSystem(ExecuteProcessor):
    """每帧执行阶段清理所有已注册的动作组件，确保动作不跨帧残留。"""

    ############################################################################################################
    def __init__(
        self,
        game: RPGGame,
        action_component_types: Mapping[str, Type[Component]] = ACTION_COMPONENT_TYPES,
    ) -> None:
        self._game: Final[RPGGame] = game
        self._registered_actions: Final[FrozenSet[Type[Component]]] = frozenset(
            action_component_types.values()
        )

    ############################################################################################################
    @override
    async def execute(self) -> None:

        # 清除行动！
        action_entities = self._game.get_group(
            Matcher(any_of=self._registered_actions)
        ).entities.copy()

        for entity in action_entities:
            for action_class in self._registered_actions:
                if entity.has(action_class):
                    entity.remove(action_class)

        # 确认一下！
        cleared_entities = self._game.get_group(
            Matcher(any_of=self._registered_actions)
        ).entities
        assert len(cleared_entities) == 0, f"entities with actions: {cleared_entities}"
