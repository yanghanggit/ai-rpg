"""每帧结束时清理所有动作组件，防止动作跨帧残留。"""

from typing import Final, FrozenSet, final, override
from ..entitas import ExecuteProcessor, Matcher
from ..entitas.components import Component
from ..game.rpg_game import RPGGame
from ..models import (
    ACTION_COMPONENT_TYPES,
)


@final
class ActionCleanupSystem(ExecuteProcessor):
    """每帧执行阶段清理所有已注册的动作组件，确保动作不跨帧残留。

    用法：将本系统注册为 ExecuteProcessor，它会在每个游戏循环中
    自动移除 ACTION_COMPONENT_TYPES 中定义的全部动作组件。
    """

    ############################################################################################################
    def __init__(self, game: RPGGame) -> None:
        self._game: RPGGame = game

    ############################################################################################################
    @override
    async def execute(self) -> None:

        # 准备数据！
        registered_actions: Final[FrozenSet[type[Component]]] = frozenset(
            ACTION_COMPONENT_TYPES.values()
        )

        # 清除行动！
        self._remove_all_action_components(registered_actions)

        # 确认一下！
        self._verify_actions_cleanup(registered_actions)

    ############################################################################################################
    def _remove_all_action_components(
        self, registered_actions: FrozenSet[type[Component]]
    ) -> None:
        """从所有实体中移除传入的动作组件集合。

        Args:
            registered_actions: 需要清理的动作组件类型集合。
        """
        action_entities = self._game.get_group(
            Matcher(any_of=registered_actions)
        ).entities.copy()

        for entity in action_entities:
            for action_class in registered_actions:
                if entity.has(action_class):
                    entity.remove(action_class)

    ############################################################################################################
    def _verify_actions_cleanup(
        self, registered_actions: FrozenSet[type[Component]]
    ) -> None:
        """断言清理完成后无任何动作组件残留。

        Args:
            registered_actions: 用于查询残留实体的动作组件类型集合。
        Raises:
            AssertionError: 若仍有实体持有动作组件。
        """
        cleared_entities = self._game.get_group(
            Matcher(any_of=registered_actions)
        ).entities
        assert len(cleared_entities) == 0, f"entities with actions: {cleared_entities}"
