"""游戏事件定义模块

事件类型用**字符串字面量**（"speak" / "whisper" / ...），不再使用自增的 IntEnum。
好处：新增事件类型时不必再"挑下一个整数"，类型名即语义，读到 JSON 就能看懂。

两条约束：
1. 具体事件的 type 必须是 Literal（不能是裸 str）——判别联合要求每个成员的判别字段是 Literal。
2. 基类 AgentEvent 的 type 是宽泛的 str（子类才能收窄成各自的 Literal），
   因此它不能作为判别联合的成员，只能放在外层 Union 里，见 AnyAgentEvent。
"""

from typing import Annotated, Literal, Union
from overrides import final
from pydantic import BaseModel, ConfigDict, Field


####################################################################################################################################
class AgentEvent(BaseModel):
    """事件基类，也是后端"未分类事件"的兜底形态（type = "none"）"""

    # 禁止额外字段：确保具体子类的 payload 无法被误判为基类事件（详见 AnyAgentEvent 处的说明）
    model_config = ConfigDict(extra="forbid")

    type: str = "none"
    message: str


####################################################################################################################################
# 说话事件
@final
class SpeakEvent(AgentEvent):
    """说话事件"""

    type: Literal["speak"] = "speak"
    actor: str
    stage: str
    target: str
    content: str


####################################################################################################################################
# 耳语事件
@final
class WhisperEvent(AgentEvent):
    """耳语事件"""

    type: Literal["whisper"] = "whisper"
    actor: str
    stage: str
    target: str
    content: str


####################################################################################################################################
# 宣布事件
@final
class AnnounceEvent(AgentEvent):
    """宣布事件"""

    type: Literal["announce"] = "announce"
    actor: str
    stage: str
    content: str


####################################################################################################################################
# 心灵语音事件
@final
class MindEvent(AgentEvent):
    """心灵语音事件"""

    type: Literal["mind"] = "mind"
    actor: str
    stage: str
    content: str


####################################################################################################################################
@final
class TransStageEvent(AgentEvent):
    """场景转换事件"""

    type: Literal["trans_stage"] = "trans_stage"
    actor: str
    stage: str
    target: str


####################################################################################################################################
@final
class CombatArbitrationEvent(AgentEvent):
    """战斗裁决事件"""

    type: Literal["combat_arbitration"] = "combat_arbitration"
    stage: str
    combat_log: str
    narrative: str


####################################################################################################################################
@final
class AppearanceUpdateEvent(AgentEvent):
    """外观更新事件"""

    type: Literal["appearance_update"] = "appearance_update"
    actor: str
    stage: str
    appearance: str


####################################################################################################################################
# 具体事件的判别联合类型：基于 type 字段（Literal 值）进行精确的反序列化。
# 注意：AgentEvent 基类的 type 字段是普通 str（非 Literal），无法作为判别式联合的
# 成员，因此单独放在外层 Union 中，由 pydantic 的 smart-union 判定
# （配合 AgentEvent.model_config.extra="forbid"，具体子类特有字段会使基类校验失败，
# 从而保证反序列化时优先精确匹配到具体子类）。
_ConcreteAgentEvent = Annotated[
    Union[
        SpeakEvent,
        WhisperEvent,
        AnnounceEvent,
        MindEvent,
        TransStageEvent,
        CombatArbitrationEvent,
        AppearanceUpdateEvent,
    ],
    Field(discriminator="type"),
]

AnyAgentEvent = Union[AgentEvent, _ConcreteAgentEvent]
####################################################################################################################################
