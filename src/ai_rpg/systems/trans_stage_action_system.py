"""场景转换动作系统模块。"""

from typing import final, override, Dict, List
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import HumanMessage, TransStageAction, HomeComponent
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.rpg_stage_transition import stage_transition


@final
class TransStageActionSystem(ReactiveProcessor):

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: DBGGame = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(TransStageAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(TransStageAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            self._process_trans_stage_action(entity)

    ####################################################################################################################################
    def _process_trans_stage_action(self, entity: Entity) -> None:
        """处理实体的场景转换动作。"""
        # 获取当前场景
        current_stage_entity = self._game.resolve_stage_entity(entity)
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
                human_message=HumanMessage(
                    content=f"# 提示！{entity.name} 触发场景转换动作失败, 找不到目标场景 {trans_stage_action.target_stage_name}."
                ),
            )
            return

        # 目前的场景移动只能在home内
        assert target_stage_entity.has(
            HomeComponent
        ), "目标场景必须是家园场景，否则就是错误，副本场景不应该被转换到"

        # 当前场景不必再移动
        if target_stage_entity == current_stage_entity:

            # 添加提示，让LLM记住错误
            self._game.add_human_message(
                entity=entity,
                human_message=HumanMessage(
                    content=f"# 提示！{entity.name} 触发场景转换动作失败, 目标场景 {trans_stage_action.target_stage_name} 与当前场景 {current_stage_entity.name} 相同."
                ),
            )
            return

        # 正式执行场景转换
        logger.debug(
            f"角色 {entity.name} 触发场景转换动作, 从场景 {current_stage_entity.name} 转换到场景 {target_stage_entity.name}."
        )
        stage_transition(self._game, {entity}, target_stage_entity)

    ####################################################################################################################################
