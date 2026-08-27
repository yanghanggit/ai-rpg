from typing import Callable, List, Sequence
from ..models.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from loguru import logger
from ..entitas import Entity
from ..models import AgentMemory, WorldState


MessagePredicate = Callable[[BaseMessage, int, Sequence[ChatMessage]], bool]


#################################################################################################################################################
class RPGAgentMemory:
    """Agent LLM 记忆操作 mixin。

    职责：封装所有基于 agent_memories 的纯读写操作，包括消息添加、查询和删除。

    Protocol 依赖声明：
        `_world: WorldState` 由 RPGGame.__init__ 注入，本类声明该属性以获得完整类型安全。
    """

    _world: WorldState  # 依赖声明：由 RPGGame.__init__ 注入

    ###############################################################################################################################################
    def get_agent_memory(self, entity: Entity) -> AgentMemory:
        """获取或创建实体的LLM记忆"""
        return self._world.agent_memories.setdefault(
            entity.name, AgentMemory(name=entity.name, messages=[])
        )

    ###############################################################################################################################################
    def remove_agent_memory(self, entity: Entity) -> None:
        """从 agent_memories 中移除实体的LLM记忆（若存在）"""
        if entity.name in self._world.agent_memories:
            logger.debug(
                f"remove_agent_memory: {entity.name} in agent_memories, pop it"
            )
            self._world.agent_memories.pop(entity.name, None)

    ###############################################################################################################################################
    def add_system_message(self, entity: Entity, system_message: SystemMessage) -> None:
        """添加系统消息到实体的LLM记忆，必须是第一条消息"""
        agent_memory = self.get_agent_memory(entity)
        assert (
            len(agent_memory.messages) == 0
        ), "system message should be the first message"
        agent_memory.messages.append(system_message)

    ###############################################################################################################################################
    def add_human_message(self, entity: Entity, human_message: HumanMessage) -> None:
        """添加用户消息到实体的LLM记忆"""
        agent_memory = self.get_agent_memory(entity)
        agent_memory.messages.append(human_message)

    ###############################################################################################################################################
    def add_ai_message(self, entity: Entity, ai_message: AIMessage) -> None:
        """添加AI响应消息到实体的LLM记忆"""
        assert ai_message.content != "", "ai_message content should not be empty"
        # 最后添加到记忆中。
        agent_memory = self.get_agent_memory(entity)
        agent_memory.messages.append(ai_message)

    ###############################################################################################################################################
    def filter_messages(
        self,
        entity: Entity,
        predicate: MessagePredicate,
        reverse_order: bool = True,
    ) -> List[ChatMessage]:
        """根据外部传入的谓词函数过滤实体记忆中的消息。"""
        messages = self.get_agent_memory(entity).messages
        found_messages: List[ChatMessage] = []

        # 生成遍历索引：默认从最新到最旧；index 始终保持原始插入顺序
        indices = (
            range(len(messages) - 1, -1, -1) if reverse_order else range(len(messages))
        )
        for index in indices:
            chat_message = messages[index]
            try:
                if predicate(chat_message, index, messages):
                    found_messages.append(chat_message)
            except Exception as e:
                logger.error(f"filter_messages error for {entity.name}: {e}")
                continue

        return found_messages

    #######################################################################################################################################
    def remove_messages(
        self,
        entity: Entity,
        messages: Sequence[BaseMessage],
    ) -> int:
        """从实体记忆中删除指定的消息对象"""
        if len(messages) == 0:
            return 0

        history = self.get_agent_memory(entity).messages
        original_length = len(history)

        # 删除指定的消息对象
        history[:] = [msg for msg in history if msg not in messages]

        deleted_count = original_length - len(history)
        if deleted_count > 0:
            logger.debug(
                f"Deleted {deleted_count} message(s) from {entity.name}'s chat history."
            )
        return deleted_count

    #######################################################################################################################################
    def remove_message_range(
        self,
        entity: Entity,
        begin_message: SystemMessage | HumanMessage | AIMessage | ToolMessage,
        end_message: SystemMessage | HumanMessage | AIMessage | ToolMessage,
    ) -> List[SystemMessage | HumanMessage | AIMessage | ToolMessage]:
        """从实体记忆中删除指定范围的消息（包含两端）"""
        assert (
            begin_message != end_message
        ), "begin_message and end_message should not be the same"

        agent_memory = self.get_agent_memory(entity)
        begin_message_index = agent_memory.messages.index(begin_message)
        end_message_index = agent_memory.messages.index(end_message) + 1

        # 保存要删除的消息
        deleted_messages = agent_memory.messages[begin_message_index:end_message_index]

        # 开始移除！！！！。
        del agent_memory.messages[begin_message_index:end_message_index]
        logger.debug(f"remove_message_range= {entity.name}")
        logger.debug(f"begin_message: \n{begin_message.model_dump_json(indent=2)}")
        logger.debug(f"end_message: \n{end_message.model_dump_json(indent=2)}")

        return deleted_messages

    #######################################################################################################################################
    def insert_messages(
        self,
        entity: Entity,
        index: int,
        messages: Sequence[SystemMessage | HumanMessage | AIMessage | ToolMessage],
    ) -> None:
        """在实体记忆的指定位置插入一段连续的消息序列"""
        if len(messages) == 0:
            return

        agent_memory = self.get_agent_memory(entity)
        agent_memory.messages[index:index] = messages
        logger.debug(
            f"insert_messages: inserted {len(messages)} message(s) at index {index} for {entity.name}"
        )

    #######################################################################################################################################
