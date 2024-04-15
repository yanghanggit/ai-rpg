from typing import Optional
from loguru import logger
from entitas.entity import Entity
from auxiliary.components import StageComponent, NPCComponent
from auxiliary.extended_context import ExtendedContext
from typing import Optional
####################################################################################################
def check_speak_enable(context: ExtendedContext, srcentity: Entity, destnpcname: str) -> bool:
    
    destnpcentity: Optional[Entity] = context.getnpc(destnpcname)
    if destnpcentity is None:
        logger.warning(f"不存在[{destnpcname}]，无法进行交谈。")
        return False
    
    stageentity = context.safe_get_stage_entity(srcentity)
    if stageentity is None:
        raise ValueError(f"未找到[{srcentity}]所在的场景。")
        return False
    
    stagecomp: StageComponent = stageentity.get(StageComponent)       
    destnpccomp: NPCComponent = destnpcentity.get(NPCComponent)
    if stagecomp.name != destnpccomp.current_stage:
        if srcentity.has(NPCComponent):
            srcnpccomp: NPCComponent = srcentity.get(NPCComponent)
            logger.warning(f"{srcnpccomp.name}在{stagecomp.name},不能与在{destnpccomp.current_stage}的{destnpcname}交谈。")
        else:
            logger.warning(f"{stagecomp.name}不能与在{destnpccomp.current_stage}的{destnpcname}交谈。")
        return False
        
    return True
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
def pre_command(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val
####################################################################################################
