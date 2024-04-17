from typing import Optional
from entitas.entity import Entity
from auxiliary.extended_context import ExtendedContext
from typing import Optional
from enum import Enum

####################################################################################################
# 错误代码
class ErrorDialogueEnable(Enum):
    VALID = 0
    TARGET_DOES_NOT_EXIST = 1
    WITHOUT_BEING_IN_STAGE = 2
    NOT_IN_THE_SAME_STAGE = 3

def dialogue_enable(context: ExtendedContext, srcentity: Entity, npcname: str) -> ErrorDialogueEnable:

    target_npc_entity: Optional[Entity] = context.getnpc(npcname)
    if target_npc_entity is None:
        # 只能对NPC说话
        return ErrorDialogueEnable.TARGET_DOES_NOT_EXIST
    
    stageentity = context.safe_get_stage_entity(srcentity)
    if stageentity is None:
        return ErrorDialogueEnable.WITHOUT_BEING_IN_STAGE
    
    target_stage = context.safe_get_stage_entity(target_npc_entity)
    if target_stage is None or target_stage != stageentity:
        return ErrorDialogueEnable.NOT_IN_THE_SAME_STAGE
    
    return ErrorDialogueEnable.VALID
####################################################################################################
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
def check_target_message_pair_format(content: str) -> bool:
    if "@" not in content or ">" not in content:
        return False
    return True