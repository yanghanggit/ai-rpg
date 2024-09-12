from entitas import Entity, Matcher  # type: ignore
from loguru import logger
from typing import Any, FrozenSet
from my_agent.agent_plan_and_action import AgentPlan, AgentAction
from rpg_game.rpg_entitas_context import RPGEntitasContext


######################################################################################################################################
def check_component_register(
    class_name: str, actions_register: FrozenSet[type[Any]]
) -> Any:
    for component in actions_register:
        if class_name == component.__name__:
            return component
    logger.warning(f"{class_name}不在{actions_register}中")
    return None


######################################################################################################################################
def check_plan(
    entity: Entity, plan: AgentPlan, actions_register: FrozenSet[type[Any]]
) -> bool:
    if len(plan._actions) == 0:
        # 走到这里
        logger.warning(f"走到这里就是request过了，但是格式在load json的时候出了问题")
        return False

    for action in plan._actions:
        if not check_available(action, actions_register):
            logger.warning(f"ActorPlanningSystem: action is not correct, {action}")
            return False
    return True


#######################################################################################################################################
def check_available(
    action: AgentAction, actions_register: FrozenSet[type[Any]]
) -> bool:
    return check_component_register(action.action_name, actions_register) is not None


#######################################################################################################################################
def add_action_component(
    entity: Entity, action: AgentAction, actions_register: FrozenSet[type[Any]]
) -> None:
    comp_class = check_component_register(action.action_name, actions_register)
    if comp_class is None:
        return
    if not entity.has(comp_class):
        entity.add(comp_class, action.name, action.values)


######################################################################################################################################
def remove_all(
    context: RPGEntitasContext, actions_register: FrozenSet[type[Any]]
) -> None:
    action_entities = context.get_group(
        Matcher(any_of=actions_register)
    ).entities.copy()
    for entity in action_entities:
        for action_class in actions_register:
            if entity.has(action_class):
                entity.remove(action_class)


######################################################################################################################################
