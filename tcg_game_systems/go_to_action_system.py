from typing import final, override
from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions import GoToAction, DeadAction
from components.components import (
    ActorComponent,
)
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from loguru import logger


@final
class GoToActionSystem(BaseActionReactiveSystem):

    ###############################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(GoToAction): GroupEvent.ADDED}

    ###############################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(GoToAction)
            and entity.has(ActorComponent)
            and not entity.has(DeadAction)
        )

    ###############################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_go_to_action(entity)

    ###############################################################################################################################################
    def _process_go_to_action(self, entity: Entity) -> None:

        # 第一步，检查是否有目标场景
        current_stage_entity = self._context.safe_get_stage_entity(entity)
        assert current_stage_entity is not None
        if current_stage_entity is None:
            # 不应该走到这里，如果走到这里就是系统的错误，actor不可以没有stage
            logger.error(f"GoToActionSystem: {entity} has no current stage")
            return

        # 第二步，检查是否有目标场景
        taget_stage_entity = self._get_go_to_target_stage_entity(entity)
        if taget_stage_entity is None:
            logger.debug(f"这里要提醒要去往的场景不存在！")
            return

        # 第三步，检查是否已经在目标场景中
        if taget_stage_entity == current_stage_entity:
            logger.debug(
                f"这里要提醒已经在目标场景中了！去往的场景和当前场景是无意义的"
            )
            return

        # 第四步，检查是否有路径连接
        next_stage_entities = self._retrieve_next_stage_entities(entity)
        if taget_stage_entity not in next_stage_entities:
            logger.debug(f"这里要提醒当前场景和目标场景之间没有路径连接！")
            return

        # 离开前的处理
        self._prepare(entity)
        # 正式离开
        self._leave_current_stage(entity)
        # 进入新的场景
        self._transition_to_target_stage(entity)
        # 进入新场景之后的处理
        self._post(entity)

    ###############################################################################################################################################
    def _prepare(self, entity: Entity) -> None:
        logger.debug(
            f"可以在离开之前将一些对本场的信息处理一下，例如对场景的印象（环境描述）和 场景内还有谁谁？"
        )

    ###############################################################################################################################################
    def _leave_current_stage(self, entity: Entity) -> None:
        # 退出场景！关键数值清空！
        actor_comp = entity.get(ActorComponent)
        entity.replace(ActorComponent, actor_comp.name, "")

    ###############################################################################################################################################
    def _transition_to_target_stage(self, entity: Entity) -> None:

        # 进入新场景！关键数值更新！
        actor_comp = entity.get(ActorComponent)
        target_stage_name = self._get_go_to_target_stage_name(entity)
        entity.replace(ActorComponent, actor_comp.name, target_stage_name)

    ###############################################################################################################################################
    def _post(self, entity: Entity) -> None:
        logger.debug(
            "进入新场景之后的处理,例如观察一遍场景内的角色有哪些？景色是怎样的？"
        )

    ###############################################################################################################################################
