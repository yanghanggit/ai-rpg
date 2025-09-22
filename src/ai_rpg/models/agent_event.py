from enum import IntEnum, unique
from overrides import final
from pydantic import BaseModel


@final
@unique
class AgentEventHead(IntEnum):
    NONE = 0
    SPEAK_EVENT = 1
    WHISPER_EVENT = 2
    ANNOUNCE_EVENT = 3
    MIND_VOICE_EVENT = 4
    TRANS_STAGE_EVENT = 5
    COMBAT_KICK_OFF_EVENT = 6
    COMBAT_COMPLETE_EVENT = 7


####################################################################################################################################
class AgentEvent(BaseModel):
    head: int = AgentEventHead.NONE
    message: str


####################################################################################################################################
# 说话事件
@final
class SpeakEvent(AgentEvent):
    head: int = AgentEventHead.SPEAK_EVENT
    actor: str
    target: str
    content: str


####################################################################################################################################
# 耳语事件
@final
class WhisperEvent(AgentEvent):
    head: int = AgentEventHead.WHISPER_EVENT
    actor: str
    target: str
    content: str


####################################################################################################################################
# 宣布事件
@final
class AnnounceEvent(AgentEvent):
    head: int = AgentEventHead.ANNOUNCE_EVENT
    actor: str
    stage: str
    content: str


####################################################################################################################################
# 心灵语音事件
@final
class MindVoiceEvent(AgentEvent):
    head: int = AgentEventHead.MIND_VOICE_EVENT
    actor: str
    content: str


####################################################################################################################################
@final
class TransStageEvent(AgentEvent):
    head: int = AgentEventHead.TRANS_STAGE_EVENT
    actor: str
    from_stage: str
    to_stage: str


####################################################################################################################################


@final
class CombatKickOffEvent(AgentEvent):
    head: int = AgentEventHead.COMBAT_KICK_OFF_EVENT
    actor: str
    description: str


####################################################################################################################################


@final
class CombatCompleteEvent(AgentEvent):
    head: int = AgentEventHead.COMBAT_COMPLETE_EVENT
    actor: str
    summary: str


####################################################################################################################################
