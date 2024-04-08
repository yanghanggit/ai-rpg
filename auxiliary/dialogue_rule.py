from typing import Optional
from loguru import logger
from entitas.entity import Entity
from auxiliary.components import StageComponent, NPCComponent
from auxiliary.extended_context import ExtendedContext

def check_speak_enable(context: ExtendedContext, srcentity: Entity, destnpcname: str) -> bool:

    destnpcentity: Optional[Entity] = context.getnpc(destnpcname)
    if destnpcentity is None:
        logger.warning(f"不存在[{destnpcname}]，无法进行交谈。")
        return False
    
    stageentity = context.get_stage_entity_by_uncertain_entity(srcentity)
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

def parse_taget_and_message(content: str) -> tuple[str, str]:
    if ">" not in content:
        return "?", content  
    if "@" not in content:
        return "?", content

    # 解析出说话者和说话内容
    target, message = content.split(">")
    target = target[1:]  # Remove the '@' symbol
    return target, message

def parse_command(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val

def parse_target_and_message_by_symbol(input_val: str) -> tuple[str, str]:
    if "@" not in input_val:
        return "", input_val
    start_index = input_val.index("@") + 1
    end_index = input_val.index(">")
    taget = input_val[start_index:end_index]
    message = input_val[end_index+1:]
    return taget, message