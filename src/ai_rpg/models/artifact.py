"""神器（Artifact）模型定义。

神器与 `Card` 同级：独立的战斗价值模型，不进道具流（不属于 `Item`/`AnyItem`），
由 Actor/Stage 通过 `ReliquaryComponent` 携带，并作为场景仲裁者的结算参数注入提示词。
"""

from enum import StrEnum, unique
from typing import List, final
from uuid import uuid4

from pydantic import BaseModel, Field

from .str_list import NormalizedStrList


###############################################################################################################################################
@final
@unique
class ArtifactPhase(StrEnum):
    """神器生效的运行点；由对应仲裁系统按此过滤自己负责的神器。"""

    POST_ARBITRATION = "PostArbitration"  # 出牌/消耗品仲裁之后


###############################################################################################################################################
@final
class Artifact(BaseModel):
    """神器：场景级战斗修正规则载体，由仲裁者（stage）依 modifiers 结算。"""

    name: str
    description: str  # 叙事锚点：神器的意象与来历，不含数值
    source: str = ""  # 来源/注入者名称；空字符串表示来源未知
    modifiers: NormalizedStrList = (
        []
    )  # 修正规则（多值）：每个元素是一条完整、独立的规则，交由仲裁 agent 逐条全部结算
    phases: List[ArtifactPhase] = [ArtifactPhase.POST_ARBITRATION]  # 生效运行点
    uuid: str = Field(default_factory=lambda: str(uuid4()))  # 全局唯一标识符
