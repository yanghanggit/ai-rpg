from enum import IntEnum, unique
from overrides import final
from pydantic import BaseModel


@final
@unique
class EventHead(IntEnum):
    NONE = 0
    SPEAK_EVENT = 1
    WHISPER_EVENT = 2
    ANNOUNCE_EVENT = 3
    MIND_EVENT = 4
    QUERY_EVENT = 5
    TRANS_STAGE_EVENT = 6
    COMBAT_KICK_OFF_EVENT = 7
    COMBAT_COMPLETE_EVENT = 8
    DISCUSSION_EVENT = 9
    NIGHT_ACTION_EVENT = 10
    VOTE_EVENT = 11


####################################################################################################################################
class AgentEvent(BaseModel):
    head: int = EventHead.NONE
    message: str


####################################################################################################################################
# 说话事件
@final
class SpeakEvent(AgentEvent):
    head: int = EventHead.SPEAK_EVENT
    actor: str
    target: str
    content: str


####################################################################################################################################
# 耳语事件
@final
class WhisperEvent(AgentEvent):
    head: int = EventHead.WHISPER_EVENT
    actor: str
    target: str
    content: str


####################################################################################################################################
# 宣布事件
@final
class AnnounceEvent(AgentEvent):
    head: int = EventHead.ANNOUNCE_EVENT
    actor: str
    stage: str
    content: str


####################################################################################################################################
# 心灵语音事件
@final
class MindEvent(AgentEvent):
    head: int = EventHead.MIND_EVENT
    actor: str
    content: str


####################################################################################################################################
@final
class TransStageEvent(AgentEvent):
    head: int = EventHead.TRANS_STAGE_EVENT
    actor: str
    from_stage: str
    to_stage: str


####################################################################################################################################


@final
class CombatKickOffEvent(AgentEvent):
    head: int = EventHead.COMBAT_KICK_OFF_EVENT
    actor: str
    description: str


####################################################################################################################################


@final
class CombatCompleteEvent(AgentEvent):
    head: int = EventHead.COMBAT_COMPLETE_EVENT
    actor: str
    summary: str


####################################################################################################################################


@final
class DiscussionEvent(AgentEvent):
    head: int = EventHead.DISCUSSION_EVENT
    actor: str
    stage: str
    content: str


####################################################################################################################################


@final
class NightActionEvent(AgentEvent):
    head: int = EventHead.NIGHT_ACTION_EVENT
    actor: str
    message: str


#####################################################################################################################################


@final
class VoteEvent(AgentEvent):
    head: int = EventHead.VOTE_EVENT
    actor: str
    target: str
