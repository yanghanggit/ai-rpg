from typing import List, Dict, Any
from ..models import AgentEvent, SessionMessage, MessageType
from pydantic import BaseModel


###############################################################################
class PlayerSession(BaseModel):
    """
    玩家会话类

    管理单个玩家在游戏过程中的状态和消息，收集并累积所有游戏事件。

    Attributes:
        name: 玩家用户名
        actor: 玩家当前控制的角色名称
        game: 游戏名称
        session_messages: 累积的所有消息/事件列表
        event_sequence: 全局事件序号
    """

    # 玩家的唯一标识符(通常是用户名)
    name: str

    # 玩家当前控制的游戏角色名称
    actor: str

    # 游戏名字
    game: str

    # 会话的完整消息/事件历史列表
    # 所有事件都会持续累积在此列表中,形成完整的会话记录
    session_messages: List[SessionMessage] = []

    # 全局事件序号,用于标识事件的顺序
    event_sequence: int = 0

    ###############################################################################
    def add_agent_event_message(self, agent_event: AgentEvent) -> None:
        """
        添加一个代理事件消息到会话历史中

        Args:
            agent_event: 代理事件对象
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

        Args:
            data: 游戏消息数据字典
        """

        # logger.debug(f"[{self.name}:{self.actor}] = add_game_message: {data}")
        game_message = SessionMessage(
            message_type=MessageType.GAME,
            data=data,
        )

        self._add_session_message(game_message)

    ###############################################################################
    def _add_session_message(self, message: SessionMessage) -> None:
        """
        内部方法：添加会话消息并分配序列号

        Args:
            message: 会话消息对象
        """
        self.event_sequence += 1
        message.sequence_id = self.event_sequence
        self.session_messages.append(message)

    ###############################################################################
    def get_messages_since(self, last_id: int) -> List[SessionMessage]:
        """
        获取指定序列号之后的所有消息（增量获取）

        Args:
            last_id: 上次获取到的最后一条消息的序列号

        Returns:
            List[SessionMessage]: 序列号大于 last_id 的所有消息列表
        """
        return [e for e in self.session_messages if e.sequence_id > last_id]

    ###############################################################################
