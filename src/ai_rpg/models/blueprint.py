from typing import Dict, List, final
from pydantic import BaseModel
from .entities import Stage, World


###############################################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class Blueprint(BaseModel):
    name: str
    player_actor: str
    campaign_setting: str
    system_rules: str  # 全局规则（角色扮演契约、副本定义、场景移动、战斗机制等）
    knowledge_base: Dict[str, List[str]]  # 蓝图关联的 RAG 知识库（按分类组织）
    stages: List[Stage]
    # 含专责插图提示词编排的世界实体（画风/构图/负面词由其 system prompt 承载）
    world_entities: List[World]


###############################################################################################################################################
