from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import TransStageAction, TransStageEvent, AgentEvent, HomeComponent
from loguru import logger


@final
class TransStageActionSystem(BaseActionReactiveSystem):

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
            self._prosses_action(entity)

    ####################################################################################################################################
    def _prosses_action(self, entity: Entity) -> None:
        current_stage_entity = self._game.safe_get_stage_entity(entity)
        assert current_stage_entity is not None, "当前场景不能为空"
        if current_stage_entity is None:
            return

        trans_stage_action = entity.get(TransStageAction)
        logger.debug(
            f"角色 {entity.name} 触发场景转换动作, 准备从场景 {current_stage_entity.name} 转换到场景 {trans_stage_action.target_stage_name}."
        )

        target_stage_entity = self._game.get_stage_entity(
            trans_stage_action.target_stage_name
        )
        assert target_stage_entity is not None, "目标场景不能为空"
        if target_stage_entity is None:
            logger.warning(
                f"角色 {entity.name} 触发场景转换动作失败, 找不到目标场景 {trans_stage_action.target_stage_name}."
            )
            self._game.notify_event(
                {entity},
                AgentEvent(
                    message=f"# {entity.name} 触发场景转换动作失败, 找不到目标场景 {trans_stage_action.target_stage_name}.",
                ),
            )
            return

        # 不能转换到当前场景
        if target_stage_entity == current_stage_entity:
            logger.warning(
                f"角色 {entity.name} 触发场景转换动作失败, 目标场景 {trans_stage_action.target_stage_name} 与当前场景 {current_stage_entity.name} 相同."
            )
            self._game.notify_event(
                {entity},
                AgentEvent(
                    message=f"# {entity.name} 触发场景转换动作失败, 目标场景 {trans_stage_action.target_stage_name} 与当前场景 {current_stage_entity.name} 相同."
                ),
            )
            return

        # 执行场景转换
        assert target_stage_entity.has(
            HomeComponent
        ), "目标场景必须是家园场景，否则就是错误，地下城场景不应该被转换到"
        self._game.stage_transition({entity}, target_stage_entity)

        # 通知事件
        self._game.notify_event(
            set({entity}),
            TransStageEvent(
                message=f"# 发生事件！{trans_stage_action.name} 从场景 {current_stage_entity.name} 转换到场景 {trans_stage_action.target_stage_name}",
                actor=trans_stage_action.name,
                from_stage=current_stage_entity.name,
                to_stage=trans_stage_action.target_stage_name,
            ),
        )

    ####################################################################################################################################
