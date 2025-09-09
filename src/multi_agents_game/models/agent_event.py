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
    COMBAT_KICK_OFF_EVENT = 5
    COMBAT_COMPLETE_EVENT = 6


class AgentEvent(BaseModel):
    head: int = AgentEventHead.NONE
    message: str


####################################################################################################################################
# 说话事件
@final
class SpeakEvent(AgentEvent):
    head: int = AgentEventHead.SPEAK_EVENT
    speaker: str
    listener: str
    dialogue: str


####################################################################################################################################
# 耳语事件
@final
class WhisperEvent(AgentEvent):
    head: int = AgentEventHead.WHISPER_EVENT
    speaker: str
    listener: str
    dialogue: str


####################################################################################################################################
# 宣布事件
@final
class AnnounceEvent(AgentEvent):
    head: int = AgentEventHead.ANNOUNCE_EVENT
    announcement_speaker: str
    event_stage: str
    announcement_message: str


####################################################################################################################################
# 心灵语音事件
@final
class MindVoiceEvent(AgentEvent):
    head: int = AgentEventHead.MIND_VOICE_EVENT
    speaker: str
    dialogue: str


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
