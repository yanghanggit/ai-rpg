"""场景转换动作系统模块。

该模块实现了游戏中角色在不同场景之间移动的系统，负责处理和验证场景转换动作，
确保场景转换的合法性，并在转换失败时提供错误提示。

主要功能：
- 验证目标场景的存在性和可访问性
- 检查场景转换的合法性（例如：只能在家园场景间移动）
- 防止无效的场景转换（例如：转换到当前场景）
- 执行角色的场景转换操作
- 处理场景转换失败的各种情况并提供反馈
"""

from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import TransStageAction, HomeComponent
from loguru import logger
from ..game.tcg_game import TCGGame


@final
class TransStageActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(TransStageAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TransStageAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_trans_stage_action(entity)

    ####################################################################################################################################
    def _process_trans_stage_action(self, entity: Entity) -> None:
        """处理实体的场景转换动作。

        该方法负责处理角色的场景转换请求，包括验证目标场景的存在性、合法性，
        检查转换的可行性，并在验证通过后执行实际的场景转换操作。

        处理流程：
        1. 获取角色当前所在的场景实体
        2. 从 TransStageAction 组件中获取目标场景名称
        3. 查找目标场景实体
        4. 验证目标场景存在性（不存在则添加错误提示并返回）
        5. 验证目标场景类型（必须是家园场景）
        6. 检查是否为无效转换（目标场景与当前场景相同）
        7. 执行场景转换操作

        Args:
            entity: 包含 TransStageAction 组件的游戏实体，代表请求转换场景的角色

        Returns:
            None

        Raises:
            AssertionError: 当前场景为空，或目标场景不是家园场景时抛出

        Note:
            - 场景转换目前仅支持家园场景之间的移动
            - 地下城场景不能作为转换目标
            - 转换失败时会通过 append_human_message 添加错误提示
            - 转换成功时会调用 stage_transition 执行实际的场景切换
        """
        # 获取当前场景
        current_stage_entity = self._game.safe_get_stage_entity(entity)
        assert current_stage_entity is not None, "当前场景不能为空"

        # 分析目标场景
        trans_stage_action = entity.get(TransStageAction)

        # 获取目标场景
        target_stage_entity = self._game.get_stage_entity(
            trans_stage_action.target_stage_name
        )

        # 判断目标场景合理性
        if target_stage_entity is None:

            # 不存在！
            self._game.add_human_message(
                entity=entity,
                message_content=f"# 提示！{entity.name} 触发场景转换动作失败, 找不到目标场景 {trans_stage_action.target_stage_name}.",
            )
            return

        # 目前的场景移动只能在home内
        assert target_stage_entity.has(
            HomeComponent
        ), "目标场景必须是家园场景，否则就是错误，地下城场景不应该被转换到"

        # 当前场景不必再移动
        if target_stage_entity == current_stage_entity:

            # 添加提示，让LLM记住错误
            self._game.add_human_message(
                entity=entity,
                message_content=f"# 提示！{entity.name} 触发场景转换动作失败, 目标场景 {trans_stage_action.target_stage_name} 与当前场景 {current_stage_entity.name} 相同.",
            )
            return

        # 正式执行场景转换
        logger.debug(
            f"角色 {entity.name} 触发场景转换动作, 从场景 {current_stage_entity.name} 转换到场景 {target_stage_entity.name}."
        )
        self._game.stage_transition({entity}, target_stage_entity)

    ####################################################################################################################################
