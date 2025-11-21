"""动作清理系统模块。

该模块实现了游戏中的动作组件清理系统，负责在每个游戏循环结束时清理所有已注册的动作组件，
确保动作不会在多个游戏帧之间残留，保持游戏状态的清洁和一致性。

主要功能：
- 在游戏循环的执行阶段自动清理所有动作组件
- 从所有包含动作组件的实体中移除这些组件
- 验证清理操作的完整性，确保没有动作组件残留
- 支持所有在 ACTION_COMPONENTS_REGISTRY 中注册的动作类型

清理机制：
- 该系统作为 ExecuteProcessor 在每个游戏循环中执行
- 清理所有注册的动作组件（如 SpeakAction、WhisperAction、AnnounceAction 等）
- 使用断言验证确保清理的完整性
- 防止动作组件在帧之间累积或重复执行

Note:
    动作组件通常表示角色的一次性行为（如对话、移动、攻击等），
    这些组件应该在处理完成后立即清理，避免影响下一帧的游戏逻辑。
"""

from typing import Final, FrozenSet, final, override
from ..entitas import ExecuteProcessor, Matcher
from ..entitas.components import Component
from ..game.rpg_game import RPGGame
from ..models import (
    ACTION_COMPONENTS_REGISTRY,
)


@final
class ActionCleanupSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: RPGGame) -> None:
        self._game: RPGGame = game_context

    ############################################################################################################
    @override
    async def execute(self) -> None:

        # 准备数据！
        registered_actions: Final[FrozenSet[type[Component]]] = frozenset(
            ACTION_COMPONENTS_REGISTRY.values()
        )

        # 清除行动！
        self._remove_all_action_components(registered_actions)

        # 确认一下！
        self._verify_actions_cleanup(registered_actions)

    ############################################################################################################
    def _remove_all_action_components(
        self, registered_actions: FrozenSet[type[Component]]
    ) -> None:
        """从所有实体中移除所有已注册的动作组件。

        该方法遍历所有包含任意注册动作组件的实体，并从这些实体中移除所有动作组件。
        这是动作清理系统的核心操作，确保每个游戏帧结束时所有动作都被清理。

        处理流程：
        1. 使用 Matcher 查询所有包含任意动作组件的实体
        2. 复制实体集合以避免迭代过程中的修改冲突
        3. 遍历每个实体
        4. 对于每种注册的动作类型，检查实体是否拥有该组件
        5. 如果拥有，则从实体中移除该动作组件

        Args:
            registered_actions: 所有已注册的动作组件类型的不可变集合，
                               通常来自 ACTION_COMPONENTS_REGISTRY

        Returns:
            None

        Note:
            - 使用 entities.copy() 避免在迭代过程中修改集合
            - 该方法会处理所有动作类型，不论实体是否真正拥有该组件
            - 移除操作是幂等的，重复移除不会产生错误
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
        """验证所有动作组件已被成功清理。

        该方法在清理操作完成后执行验证检查，确保没有任何动作组件残留在实体中。
        如果发现任何残留的动作组件，将触发断言失败，帮助开发者及时发现清理逻辑的问题。

        验证流程：
        1. 查询所有仍然包含任意动作组件的实体
        2. 断言实体集合为空（长度为 0）
        3. 如果断言失败，输出包含残留动作的实体信息

        Args:
            registered_actions: 所有已注册的动作组件类型的不可变集合，
                               与清理操作使用的集合相同

        Returns:
            None

        Raises:
            AssertionError: 当发现任何实体仍然包含动作组件时抛出，
                           错误信息包含残留动作的实体列表

        Note:
            - 这是一个防御性检查，用于确保清理逻辑的正确性
            - 在生产环境中，断言失败表示清理系统存在严重问题
            - 该方法应该在 _remove_all_action_components 之后立即调用
            - 如果频繁触发断言，需要检查动作组件的注册和清理逻辑
        """
        cleared_entities = self._game.get_group(
            Matcher(any_of=registered_actions)
        ).entities
        assert len(cleared_entities) == 0, f"entities with actions: {cleared_entities}"
