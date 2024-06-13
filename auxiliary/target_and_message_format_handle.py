from typing import Optional
from entitas.entity import Entity
from auxiliary.extended_context import ExtendedContext
from typing import Optional
from enum import Enum

####################################################################################################
# 错误代码
class ErrorConversationEnable(Enum):
    VALID = 0
    TARGET_DOES_NOT_EXIST = 1
    WITHOUT_BEING_IN_STAGE = 2
    NOT_IN_THE_SAME_STAGE = 3

# 检查是否可以对话
def conversation_check(context: ExtendedContext, srcentity: Entity, target_name: str) -> ErrorConversationEnable:

    target_entity: Optional[Entity] = context.get_actor_entity(target_name)
    if target_entity is None:
        # 只能对Actor说话?
        return ErrorConversationEnable.TARGET_DOES_NOT_EXIST
    
    stageentity = context.safe_get_stage_entity(srcentity)
    if stageentity is None:
        return ErrorConversationEnable.WITHOUT_BEING_IN_STAGE
    
    target_stage = context.safe_get_stage_entity(target_entity)
    if target_stage is None or target_stage != stageentity:
        return ErrorConversationEnable.NOT_IN_THE_SAME_STAGE
    
    return ErrorConversationEnable.VALID

####################################################################################################
class ErrorUsePropEnable(Enum):
    VALID = 0
    TARGET_DOES_NOT_EXIST = 1
    WITHOUT_BEING_IN_STAGE = 2
    NOT_IN_THE_SAME_STAGE = 3

# 检查是否可以使用道具
def use_prop_check(context: ExtendedContext, srcentity: Entity, targetname: str) -> ErrorUsePropEnable:

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
####################################################################################################
# 我方定义的规则字符串
def parse_target_and_message(content: str) -> tuple[Optional[str], Optional[str]]:
    # 检查是否包含'@'和'>'符号
    if "@" not in content or ">" not in content:
        return None, content

    # 检查'@'是否出现在'>'之前
    at_index = content.find("@")
    gt_index = content.find(">")
    if at_index > gt_index:
        return None, content

    # 提取目标和消息
    try:
        target = content[at_index + 1:gt_index].strip()
        message = content[gt_index + 1:].strip()

        # 确保目标和消息不为空
        if not target or not message:
            return None, content

        return target, message
    except Exception as e:
        # 如果有任何异常，返回原始内容和异常提示
        return None, content
####################################################################################################
# 是否是有效的目标和消息格式
def check_target_and_message_format(content: str) -> bool:
    if "@" not in content or ">" not in content:
        return False
    return True
####################################################################################################