from typing import Optional
from entitas.entity import Entity
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import Optional
from enum import Enum


#################################################################################################################################
class ErrorUsePropEnable(Enum):
    VALID = 0
    TARGET_DOES_NOT_EXIST = 1
    WITHOUT_BEING_IN_STAGE = 2
    NOT_IN_THE_SAME_STAGE = 3


# 检查是否可以使用道具
def use_prop_check(
    context: RPGEntitasContext, srcentity: Entity, targetname: str
) -> ErrorUsePropEnable:

    src_stage = context.safe_get_stage_entity(srcentity)
    if src_stage is None:
        return ErrorUsePropEnable.WITHOUT_BEING_IN_STAGE

    final_target_entity: Optional[Entity] = None
    target_actor_entity: Optional[Entity] = context.get_actor_entity(targetname)
    target_stage_entity: Optional[Entity] = context.get_stage_entity(targetname)

    if target_actor_entity is not None:
        final_target_entity = target_actor_entity
    elif target_stage_entity is not None:
        final_target_entity = target_stage_entity

    if final_target_entity is None:
        return ErrorUsePropEnable.TARGET_DOES_NOT_EXIST

    target_stage = context.safe_get_stage_entity(final_target_entity)
    if target_stage is None or target_stage != src_stage:
        return ErrorUsePropEnable.NOT_IN_THE_SAME_STAGE

    return ErrorUsePropEnable.VALID


#################################################################################################################################
