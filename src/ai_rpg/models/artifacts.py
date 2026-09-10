"""
Artifact / Artefact (神器/古物)：比“Relic”的使用更普遍，是许多游戏的标准命名之一。它强调物品的强大力量和古老属性，是品类里的“万金油”。
"""

from enum import StrEnum, unique
from typing import List, final
from uuid import uuid4

from pydantic import BaseModel, Field


###############################################################################################################################################
@final
@unique
class ArtifactTag(StrEnum):
    """神器运行点标记（tag）：标记神器在哪个运行点触发。"""

    POST_ARBITRATION = "post_arbitration"  # 出牌/使用消耗品结算之后


###############################################################################################################################################
class Artifact(BaseModel):
    """Artifact / Artefact (神器/古物)"""

    name: str
    description: str
    modifiers: List[str] = []  # 物品属性修饰符
    tags: List[ArtifactTag] = []  # 标记，用于检索与运行点匹配
    source: str = ""  # 来源标记（内容作者赋值，供 LLM 识别来源者）
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符


###############################################################################################################################################
