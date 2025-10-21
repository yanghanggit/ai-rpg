"""
玩家会话管理模块

本模块定义了玩家会话(PlayerSession)类,用于管理单个玩家在游戏过程中的状态和消息。

主要职责:
1. 存储玩家的基本信息(名称、控制的角色)
2. 管理会话期间产生的所有消息/事件
3. 作为游戏状态与客户端通信的桥梁

设计思路:
- 采用事件驱动模式,所有游戏事件都通过此类记录
- 消息列表持续累积,记录完整的会话历史
- 简单直接的设计,避免过度工程化

相关设计文档: docs/development-logs/消息可靠性传递方案设计.md
"""

from typing import List, Dict, Any
from ..models import AgentEvent, SessionMessage, MessageType
from pydantic import BaseModel


###############################################################################
class PlayerSession(BaseModel):
    """
    玩家会话类

    管理单个玩家在游戏过程中的状态和消息。
    用于收集游戏流程(Pipeline)执行期间产生的所有事件,
    并将这些事件持续累积形成完整的会话历史。

    核心工作流程:
    1. 游戏初始化时创建PlayerSession实例
    2. Pipeline执行期间,所有事件通过add_agent_event_message()记录
    3. session_messages持续累积所有历史事件
    4. 客户端可随时访问完整的消息历史

    属性:
        name: 玩家用户名/标识符
        actor: 玩家当前控制的游戏角色名称
        session_messages: 累积的所有消息/事件列表(完整历史)

    使用示例:
        >>> session = PlayerSession(name="player1", actor="角色.主持人")
        >>> session.add_agent_event_message(event1)
        >>> session.add_agent_event_message(event2)
        >>> # session_messages 包含完整的事件历史
        >>> all_history = session.session_messages
    """

    # 玩家的唯一标识符(通常是用户名)
    name: str

    # 玩家当前控制的游戏角色名称
    actor: str

    # 会话的完整消息/事件历史列表
    # 所有事件都会持续累积在此列表中,形成完整的会话记录
    session_messages: List[SessionMessage] = []

    # 全局事件序号,用于标识事件的顺序
    event_sequence: int = 0

    ###############################################################################
    def add_agent_event_message(self, agent_event: AgentEvent) -> None:
        """
        添加一个代理事件消息到会话历史中

        当游戏逻辑执行过程中产生事件时,通过此方法记录到会话历史中。
        事件会被持久化保存在session_messages列表中,形成完整的游戏流程记录。

        工作流程:
        1. 接收AgentEvent对象(包含事件的详细信息)
        2. 将其封装为SessionMessage(带有消息类型标识)
        3. 追加到session_messages历史列表中
        4. 记录调试日志便于追踪

        参数:
            agent_event: 代理事件对象,包含:
                - name: 事件名称
                - message: 事件消息内容
                - agent_name: 触发事件的代理名称
                - 其他相关数据

        返回:
            无返回值(void)

        注意:
            - 此方法会在Pipeline执行期间被频繁调用
            - 所有事件会永久累积在session_messages中
            - 如需限制内存占用,应在上层实现历史清理机制

        使用示例:
            >>> event = AgentEvent(
            ...     name="角色行动",
            ...     message="狼人选择了击杀目标",
            ...     agent_name="狼人1"
            ... )
            >>> player_session.add_agent_event_message(event)
            >>> # 事件已添加到历史记录中
        """
        # 记录调试日志,方便追踪事件流
        # logger.debug(
        #     f"[{self.name}:{self.actor}] = add_agent_event_message: {agent_event.model_dump_json()}"
        # )

        # 将AgentEvent封装为SessionMessage并追加到列表
        # MessageType.AGENT_EVENT 标识这是一个代理事件类型的消息
        agent_event_message = SessionMessage(
            message_type=MessageType.AGENT_EVENT,  # 消息类型标识
            data=agent_event.model_dump(),  # 将事件序列化为字典
        )

        self._add_session_message(agent_event_message)

    ###############################################################################
    def add_game_message(self, data: Dict[str, Any]) -> None:
        """
        添加一个游戏消息到会话历史中
        """

        # logger.debug(f"[{self.name}:{self.actor}] = add_game_message: {data}")

        game_message = SessionMessage(
            message_type=MessageType.GAME,
            data=data,
        )

        self._add_session_message(game_message)

    ###############################################################################
    def _add_session_message(self, message: SessionMessage) -> None:
        # 为消息分配递增的序列号并添加到列表
        self.event_sequence += 1
        message.sequence_id = self.event_sequence
        self.session_messages.append(message)

    ###############################################################################
    # 3. 服务器返回增量事件
    def get_messages_since(self, last_id: int) -> List[SessionMessage]:
        return [e for e in self.session_messages if e.sequence_id > last_id]

    ###############################################################################
