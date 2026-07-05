"""游戏事件定义模块"""

from enum import IntEnum, unique
from typing import Annotated, Literal, Union
from overrides import final
from pydantic import BaseModel, Field


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

    type: int = EventType.NONE
    message: str


####################################################################################################################################
# 说话事件
@final
class SpeakEvent(AgentEvent):
    """说话事件"""

    type: Literal[EventType.SPEAK] = EventType.SPEAK
    actor: str
    target: str
    content: str


####################################################################################################################################
# 耳语事件
@final
class WhisperEvent(AgentEvent):
    """耳语事件"""

    type: Literal[EventType.WHISPER] = EventType.WHISPER
    actor: str
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
    content: str


####################################################################################################################################
@final
class QueryEvent(AgentEvent):
    """查询事件"""

    type: Literal[EventType.QUERY] = EventType.QUERY
    actor: str
    question: str


####################################################################################################################################
@final
class TransStageEvent(AgentEvent):
    """场景转换事件"""

    type: Literal[EventType.TRANS_STAGE] = EventType.TRANS_STAGE
    actor: str
    from_stage: str
    to_stage: str


####################################################################################################################################
@final
class CombatInitiationEvent(AgentEvent):
    """战斗发起事件"""

    type: Literal[EventType.COMBAT_INITIATION] = EventType.COMBAT_INITIATION
    actor: str


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
    summary: str


####################################################################################################################################
@final
class AppearanceUpdateEvent(AgentEvent):
    """外观更新事件"""

    type: Literal[EventType.APPEARANCE_UPDATE] = EventType.APPEARANCE_UPDATE
    actor: str
    appearance: str


####################################################################################################################################
# 判别联合类型：可基于 head 字段进行精确的反序列化
AnyAgentEvent = Annotated[
    Union[
        AgentEvent,
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
####################################################################################################################################
