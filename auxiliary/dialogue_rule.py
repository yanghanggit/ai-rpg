from typing import Optional
from loguru import logger
from entitas.entity import Entity
from auxiliary.components import StageComponent, NPCComponent
from auxiliary.extended_context import ExtendedContext

def check_speak_enable(context: ExtendedContext, src_entity: Entity, dest_name: str) -> bool:

    npc_entity: Optional[Entity] = context.getnpc(dest_name)
    if npc_entity is None:
        logger.warning(f"不存在{dest_name}，无法进行交谈。")
        return False

    src_current_stage_comp: Optional[StageComponent] = context.get_stagecomponent_by_uncertain_entity(src_entity)  
    if src_current_stage_comp is None:
        logger.warning(f"StageComponent not found for {src_entity}")
        return False  
        
    dest_npc_comp: NPCComponent = npc_entity.get(NPCComponent)
    if src_current_stage_comp.name != dest_npc_comp.current_stage:
        if src_entity.has(NPCComponent):
            logger.warning(f"{src_entity.get(NPCComponent).name}在{src_current_stage_comp.name},不能与在{dest_npc_comp.current_stage}的{dest_name}交谈。")
        else:
            logger.warning(f"{src_current_stage_comp.name}不能与在{dest_npc_comp.current_stage}的{dest_name}交谈。")
        return False
        
    return True

def parse_taget_and_message(content: str) -> tuple[str, str]:
    # 解析出说话者和说话内容
    target, message = content.split(">")
    target = target[1:]  # Remove the '@' symbol
    return target, message