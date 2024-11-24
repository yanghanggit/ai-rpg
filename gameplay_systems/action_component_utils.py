from entitas import Entity, Matcher  # type: ignore
from loguru import logger
from typing import Any, FrozenSet, Optional
from my_agent.agent_plan import AgentPlanResponse, AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from enum import Enum
from my_components.action_components import (
    ACTOR_AVAILABLE_ACTIONS_REGISTER,
    STAGE_AVAILABLE_ACTIONS_REGISTER,
)
from my_components.components import ActorComponent, StageComponent


class ConversationError(Enum):
    VALID = 0
    INVALID_TARGET = 1
    NO_STAGE = 2
    NOT_SAME_STAGE = 3


# 检查是否可以对话
def validate_conversation(
    context: RPGEntitasContext, stage_or_actor_entity: Entity, target_name: str
) -> ConversationError:

    actor_entity: Optional[Entity] = context.get_actor_entity(target_name)
    if actor_entity is None:
        return ConversationError.INVALID_TARGET

    current_stage_entity = context.safe_get_stage_entity(stage_or_actor_entity)
    if current_stage_entity is None:
        return ConversationError.NO_STAGE

    target_stage_entity = context.safe_get_stage_entity(actor_entity)
    if target_stage_entity != current_stage_entity:
        return ConversationError.NOT_SAME_STAGE

    return ConversationError.VALID


######################################################################################################################################
######################################################################################################################################
######################################################################################################################################


######################################################################################################################################
def _retrieve_registered_component(
    class_name: str, registered_components: FrozenSet[type[Any]]
) -> Any:
    for component in registered_components:
        if class_name == component.__name__:
            return component
    logger.warning(f"{class_name}不在{registered_components}中")
    return None


######################################################################################################################################
def _validate_actions(
    plan_response: AgentPlanResponse,
    registered_actions: FrozenSet[type[Any]],
) -> bool:
    if len(plan_response._actions) == 0:
        return False

    for action in plan_response._actions:
        if (
            _retrieve_registered_component(action.action_name, registered_actions)
            is None
        ):
            logger.warning(f"action is not correct, {action}")
            return False
    return True


#######################################################################################################################################
def _add_action(
    entity: Entity, action: AgentAction, registered_actions: FrozenSet[type[Any]]
) -> None:
    comp_class = _retrieve_registered_component(action.action_name, registered_actions)
    if comp_class is None:
        return
    entity.replace(comp_class, action.name, action.values)


######################################################################################################################################
def clear_registered_actions(
    context: RPGEntitasContext, registered_actions: FrozenSet[type[Any]]
) -> None:
    entities = context.get_group(Matcher(any_of=registered_actions)).entities.copy()
    for entity in entities:
        for action_class in registered_actions:
            if entity.has(action_class):
                entity.remove(action_class)


######################################################################################################################################
def add_actor_actions(
    context: RPGEntitasContext,
    actor_entity: Entity,
    actor_planning_response: AgentPlanResponse,
    registered_actions: FrozenSet[type[Any]] = ACTOR_AVAILABLE_ACTIONS_REGISTER,
) -> bool:

    assert actor_entity.has(
        ActorComponent
    ), f"actor_entity has no ActorComponent, {actor_entity}"

    if not _validate_actions(actor_planning_response, registered_actions):
        logger.warning(
            f"add_actor_actions, {actor_planning_response.raw_response_content}"
        )
        return False

    ## 不能停了，只能一直继续
    for action in actor_planning_response._actions:
        _add_action(actor_entity, action, registered_actions)

    return True


######################################################################################################################################
def add_stage_actions(
    context: RPGEntitasContext,
    stage_entity: Entity,
    stage_planning_response: AgentPlanResponse,
    registered_actions: FrozenSet[type[Any]] = STAGE_AVAILABLE_ACTIONS_REGISTER,
) -> bool:

    assert stage_entity.has(
        StageComponent
    ), f"stage_entity has no StageComponent, {stage_entity}"

    if not _validate_actions(stage_planning_response, registered_actions):
        logger.warning(
            f"add_stage_actions failed, {stage_planning_response.raw_response_content}"
        )
        return False

    ## 不能停了，只能一直继续
    for action in stage_planning_response._actions:
        _add_action(stage_entity, action, registered_actions)

    return True


######################################################################################################################################
