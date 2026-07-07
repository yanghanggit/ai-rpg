"""游戏事件定义模块"""

from enum import IntEnum, unique
from typing import Annotated, Literal, Union
from overrides import final
from pydantic import BaseModel, ConfigDict, Field


@final
@unique
class EventType(IntEnum):
    """事件类型枚举"""

    NONE = 0
    SPEAK = 1
    WHISPER = 2
    ANNOUNCE = 3
    MIND = 4
    QUERY = 5
    TRANS_STAGE = 6
    COMBAT_INITIATION = 7
    COMBAT_ARBITRATION = 8
    COMBAT_ARCHIVE = 9
    APPEARANCE_UPDATE = 10


####################################################################################################################################
class AgentEvent(BaseModel):
    """事件基类"""

    # 禁止额外字段：确保具体子类的 payload 无法被误判为基类事件（详见 AnyAgentEvent 处的说明）
    model_config = ConfigDict(extra="forbid")

    type: int = EventType.NONE
    message: str


####################################################################################################################################
# 说话事件
@final
class SpeakEvent(AgentEvent):
    """说话事件"""

    type: Literal[EventType.SPEAK] = EventType.SPEAK
    actor: str
    stage: str
    target: str
    content: str


####################################################################################################################################
# 耳语事件
@final
class WhisperEvent(AgentEvent):
    """耳语事件"""

    type: Literal[EventType.WHISPER] = EventType.WHISPER
    actor: str
    stage: str
    target: str
    content: str


####################################################################################################################################
# 宣布事件
@final
class AnnounceEvent(AgentEvent):
    """宣布事件"""

    type: Literal[EventType.ANNOUNCE] = EventType.ANNOUNCE
    actor: str
    stage: str
    content: str


####################################################################################################################################
# 心灵语音事件
@final
class MindEvent(AgentEvent):
    """心灵语音事件"""

    type: Literal[EventType.MIND] = EventType.MIND
    actor: str
    stage: str
    content: str


####################################################################################################################################
@final
class QueryEvent(AgentEvent):
    """查询事件"""

    type: Literal[EventType.QUERY] = EventType.QUERY
    actor: str
    stage: str
    question: str


####################################################################################################################################
@final
class TransStageEvent(AgentEvent):
    """场景转换事件"""

    type: Literal[EventType.TRANS_STAGE] = EventType.TRANS_STAGE
    actor: str
    stage: str
    target: str


####################################################################################################################################
@final
class CombatInitiationEvent(AgentEvent):
    """战斗发起事件"""

    type: Literal[EventType.COMBAT_INITIATION] = EventType.COMBAT_INITIATION
    actor: str
    stage: str


####################################################################################################################################


@final
class CombatArbitrationEvent(AgentEvent):
    """战斗裁决事件"""

    type: Literal[EventType.COMBAT_ARBITRATION] = EventType.COMBAT_ARBITRATION
    stage: str
    combat_log: str
    narrative: str


####################################################################################################################################
@final
class CombatArchiveEvent(AgentEvent):
    """战斗归档事件"""

    type: Literal[EventType.COMBAT_ARCHIVE] = EventType.COMBAT_ARCHIVE
    actor: str
    stage: str
    summary: str


####################################################################################################################################
@final
class AppearanceUpdateEvent(AgentEvent):
    """外观更新事件"""

    type: Literal[EventType.APPEARANCE_UPDATE] = EventType.APPEARANCE_UPDATE
    actor: str
    stage: str
    appearance: str


####################################################################################################################################
# 具体事件的判别联合类型：基于 type 字段（Literal 值）进行精确的反序列化。
# 注意：AgentEvent 基类的 type 字段是普通 int（非 Literal），无法作为判别式联合的
# 成员，因此单独放在外层 Union 中，由 pydantic 的 smart-union 判定
# （配合 AgentEvent.model_config.extra="forbid"，具体子类特有字段会使基类校验失败，
# 从而保证反序列化时优先精确匹配到具体子类）。
_ConcreteAgentEvent = Annotated[
    Union[
        SpeakEvent,
        WhisperEvent,
        AnnounceEvent,
        MindEvent,
        QueryEvent,
        TransStageEvent,
        CombatInitiationEvent,
        CombatArbitrationEvent,
        CombatArchiveEvent,
        AppearanceUpdateEvent,
    ],
    Field(discriminator="type"),
]

AnyAgentEvent = Union[AgentEvent, _ConcreteAgentEvent]
####################################################################################################################################
