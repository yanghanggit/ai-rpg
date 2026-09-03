from typing import Dict, List, final
from pydantic import BaseModel
from .entities import Stage, World
from .artifacts import Artifact


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
    world_entities: List[World]
    artifacts: List[Artifact] = []  # 蓝图初始世界神器/古物库


###############################################################################################################################################
