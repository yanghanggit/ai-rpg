from typing import Optional
from entitas.entity import Entity
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import Optional
from enum import Enum


class ErrorConversation(Enum):
    VALID = 0
    INVALID_TARGET = 1
    NO_STAGE = 2
    NOT_SAME_STAGE = 3


# 检查是否可以对话
def check_conversation(
    context: RPGEntitasContext, actor_or_stage_entity: Entity, target_name: str
) -> ErrorConversation:

    must_be_actor_entity: Optional[Entity] = context.get_actor_entity(target_name)
    if must_be_actor_entity is None:
        return ErrorConversation.INVALID_TARGET

    current_stage_entity = context.safe_get_stage_entity(actor_or_stage_entity)
    if current_stage_entity is None:
        return ErrorConversation.NO_STAGE

    target_stage_entity = context.safe_get_stage_entity(must_be_actor_entity)
    if target_stage_entity != current_stage_entity:
        return ErrorConversation.NOT_SAME_STAGE

    return ErrorConversation.VALID
