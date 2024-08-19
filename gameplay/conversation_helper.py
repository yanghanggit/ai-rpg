from typing import Optional
from entitas.entity import Entity
from rpg_game.rpg_entitas_context import RPGEntitasContext
from typing import Optional
from enum import Enum


# 错误代码
class ErrorConversationEnable(Enum):
    VALID = 0
    TARGET_DOES_NOT_EXIST = 1
    WITHOUT_BEING_IN_STAGE = 2
    NOT_IN_THE_SAME_STAGE = 3


# 检查是否可以对话
def check_conversation_enable(
    context: RPGEntitasContext, actor_or_stage_entity: Entity, target_name: str
) -> ErrorConversationEnable:

    must_be_actor_entity: Optional[Entity] = context.get_actor_entity(target_name)
    if must_be_actor_entity is None:
        # 只能对Actor说话?
        return ErrorConversationEnable.TARGET_DOES_NOT_EXIST

    current_stage_entity = context.safe_get_stage_entity(actor_or_stage_entity)
    if current_stage_entity is None:
        return ErrorConversationEnable.WITHOUT_BEING_IN_STAGE

    target_stage_entity = context.safe_get_stage_entity(must_be_actor_entity)
    if target_stage_entity is None or target_stage_entity != current_stage_entity:
        return ErrorConversationEnable.NOT_IN_THE_SAME_STAGE

    return ErrorConversationEnable.VALID
