from typing import Dict, List, final
from pydantic import BaseModel
from .entities import Stage, World
from .items import AnyItem
from .artifacts import Artifact


###############################################################################################################################################################
# 生成世界的根文件，就是世界的起点
@final
class Blueprint(BaseModel):
    name: str
    player_actor: str
    campaign_setting: str
    knowledge_base: Dict[str, List[str]]  # 蓝图关联的 RAG 知识库（按分类组织）
    stages: List[Stage]
    world_entities: List[World]
    storage_entity: str  # 全局储物箱实体名
    storage: List[AnyItem] = []  # 蓝图初始储物箱道具库
    inventory: List[AnyItem] = []  # 蓝图初始玩家背包道具库
    artifacts: List[Artifact] = []  # 蓝图初始世界神器/古物库


###############################################################################################################################################
