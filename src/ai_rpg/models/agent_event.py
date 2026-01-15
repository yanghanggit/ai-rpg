from enum import IntEnum, unique
from overrides import final
from pydantic import BaseModel


@final
@unique
class EventHead(IntEnum):
    """事件类型头枚举。

    定义了游戏中所有可能的Agent事件类型标识符。
    每个事件类型对应一个唯一的整数值，用于在事件分发和处理时
    快速识别事件类型。

    Attributes:
        NONE: 空事件，默认值
        SPEAK_EVENT: 说话事件，公开发言
        WHISPER_EVENT: 耳语事件，私密交流
        ANNOUNCE_EVENT: 宣布事件，系统通知
        MIND_EVENT: 心灵语音事件，内心独白
        QUERY_EVENT: 查询事件
        TRANS_STAGE_EVENT: 场景转换事件
        COMBAT_ARBITRATION_EVENT: 战斗裁决事件
        COMBAT_ARCHIVE_EVENT: 战斗归档事件
        DISCUSSION_EVENT: 讨论事件
        NIGHT_ACTION_EVENT: 夜间行动事件
        VOTE_EVENT: 投票事件
    """

    NONE = 0
    SPEAK_EVENT = 1
    WHISPER_EVENT = 2
    ANNOUNCE_EVENT = 3
    MIND_EVENT = 4
    QUERY_EVENT = 5
    TRANS_STAGE_EVENT = 6
    COMBAT_ARBITRATION_EVENT = 7
    COMBAT_ARCHIVE_EVENT = 8


####################################################################################################################################
class AgentEvent(BaseModel):
    """事件基类。

    所有Agent事件的基础类，定义了事件的通用结构。
    每个事件都包含一个类型头（head）和一条消息（message）。

    Attributes:
        head: 事件类型标识符，对应EventHead枚举值
        message: 事件的文本消息内容
    """

    head: int = EventHead.NONE
    message: str


####################################################################################################################################
# 说话事件
@final
class SpeakEvent(AgentEvent):
    """说话事件。

    表示一个角色对另一个角色公开发言的事件。
    该事件对当前场景中的所有角色可见。

    Attributes:
        head: 事件类型，固定为SPEAK_EVENT
        actor: 发言者的角色名称
        target: 接收者的角色名称
        content: 发言的具体内容
    """

    head: int = EventHead.SPEAK_EVENT
    actor: str
    target: str
    content: str


####################################################################################################################################
# 耳语事件
@final
class WhisperEvent(AgentEvent):
    """耳语事件。

    表示一个角色对另一个角色私密交流的事件。
    该事件仅对发言者和接收者可见，其他角色无法观察到。

    Attributes:
        head: 事件类型，固定为WHISPER_EVENT
        actor: 发言者的角色名称
        target: 接收者的角色名称
        content: 耳语的具体内容
    """

    head: int = EventHead.WHISPER_EVENT
    actor: str
    target: str
    content: str


####################################################################################################################################
# 宣布事件
@final
class AnnounceEvent(AgentEvent):
    """宣布事件。

    表示系统或角色在特定场景中发布公告的事件。
    通常用于重要通知、系统消息或场景级别的广播。

    Attributes:
        head: 事件类型，固定为ANNOUNCE_EVENT
        actor: 发布者的角色名称
        stage: 发布宣布的场景名称
        content: 宣布的具体内容
    """

    head: int = EventHead.ANNOUNCE_EVENT
    actor: str
    stage: str
    content: str


####################################################################################################################################
# 心灵语音事件
@final
class MindEvent(AgentEvent):
    """心灵语音事件。

    表示角色的内心独白或思考过程的事件。
    该事件仅对角色自己可见，不会被其他角色观察到，
    用于记录角色的内心活动和思维过程。

    Attributes:
        head: 事件类型，固定为MIND_EVENT
        actor: 思考者的角色名称
        content: 内心独登的具体内容
    """

    head: int = EventHead.MIND_EVENT
    actor: str
    content: str


####################################################################################################################################
@final
class TransStageEvent(AgentEvent):
    """场景转换事件。

    表示角色从一个场景移动到另一个场景的事件。
    记录了角色的空间位置变化，用于跟踪角色的移动轨迹。

    Attributes:
        head: 事件类型，固定为TRANS_STAGE_EVENT
        actor: 移动的角色名称
        from_stage: 离开的场景名称
        to_stage: 进入的场景名称
    """

    head: int = EventHead.TRANS_STAGE_EVENT
    actor: str
    from_stage: str
    to_stage: str


####################################################################################################################################


@final
class CombatArbitrationEvent(AgentEvent):
    """战斗裁决事件。

    表示战斗系统对战斗过程进行裁决并生成叙事描述的事件。
    包含战斗的原始日志和AI生成的战斗叙事，用于将战斗数据
    转化为易于理解的文本描述。

    Attributes:
        head: 事件类型，固定为COMBAT_ARBITRATION_EVENT
        stage: 战斗发生的场景名称
        combat_log: 战斗的原始日志数据
        narrative: AI生成的战斗叙事文本
    """

    head: int = EventHead.COMBAT_ARBITRATION_EVENT
    stage: str
    combat_log: str
    narrative: str


####################################################################################################################################


@final
class CombatArchiveEvent(AgentEvent):
    """战斗归档事件。

    表示战斗结束后将角色的战斗经历归档到记忆系统的事件。
    包含了AI生成的战斗总结，用于存储到角色的知识库中，
    作为后续回忆和决策的参考。

    Attributes:
        head: 事件类型，固定为COMBAT_ARCHIVE_EVENT
        actor: 参与战斗的角色名称
        summary: AI生成的战斗经历总结
    """

    head: int = EventHead.COMBAT_ARCHIVE_EVENT
    actor: str
    summary: str


####################################################################################################################################
