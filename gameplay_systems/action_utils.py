from entitas import Entity, Matcher  # type: ignore
from loguru import logger
from typing import Any, FrozenSet, Optional
from my_agent.agent_plan import AgentPlanResponse, AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from enum import Enum


######################################################################################################################################
def retrieve_registered_component(
    class_name: str, registered_components: FrozenSet[type[Any]]
) -> Any:
    for component in registered_components:
        if class_name == component.__name__:
            return component
    logger.warning(f"{class_name}不在{registered_components}中")
    return None


######################################################################################################################################
def validate_actions(
    plan_response: AgentPlanResponse,
    registered_actions: FrozenSet[type[Any]],
) -> bool:
    if len(plan_response._actions) == 0:
        # 走到这里
        # logger.warning(f"走到这里就是request过了，但是格式在load json的时候出了问题")
        return False

    for action in plan_response._actions:
        if (
            retrieve_registered_component(action.action_name, registered_actions)
            is None
        ):
            logger.warning(f"action is not correct, {action}")
            return False
    return True


#######################################################################################################################################
def add_action(
    entity: Entity, action: AgentAction, registered_actions: FrozenSet[type[Any]]
) -> None:
    comp_class = retrieve_registered_component(action.action_name, registered_actions)
    if comp_class is None:
        return
    entity.replace(comp_class, action.name, action.values)


######################################################################################################################################
def remove_actions(
    context: RPGEntitasContext, registered_actions: FrozenSet[type[Any]]
) -> None:
    entities = context.get_group(Matcher(any_of=registered_actions)).entities.copy()
    for entity in entities:
        for action_class in registered_actions:
            if entity.has(action_class):
                entity.remove(action_class)


######################################################################################################################################


class ConversationError(Enum):
    VALID = 0
    INVALID_TARGET = 1
    NO_STAGE = 2
    NOT_SAME_STAGE = 3


# 检查是否可以对话
def validate_conversation(
    context: RPGEntitasContext, actor_or_stage_entity: Entity, target_name: str
) -> ConversationError:

    must_be_actor_entity: Optional[Entity] = context.get_actor_entity(target_name)
    if must_be_actor_entity is None:
        return ConversationError.INVALID_TARGET

    current_stage_entity = context.safe_get_stage_entity(actor_or_stage_entity)
    if current_stage_entity is None:
        return ConversationError.NO_STAGE

    target_stage_entity = context.safe_get_stage_entity(must_be_actor_entity)
    if target_stage_entity != current_stage_entity:
        return ConversationError.NOT_SAME_STAGE

    return ConversationError.VALID
