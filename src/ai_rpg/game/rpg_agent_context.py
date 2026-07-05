from typing import Any, Dict, List, Sequence
from ..models.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from loguru import logger
from ..entitas import Entity
from ..models import AgentContext, World


#################################################################################################################################################
class RPGAgentContext:
    """Agent LLM 上下文操作 mixin。

    职责：封装所有基于 agents_context 的纯读写操作，包括消息添加、查询和删除。

    Protocol 依赖声明：
        `_world: World` 由 RPGGame.__init__ 注入，本类声明该属性以获得完整类型安全。
    """

    _world: World  # 依赖声明：由 RPGGame.__init__ 注入

    ###############################################################################################################################################
    def get_agent_context(self, entity: Entity) -> AgentContext:
        """获取或创建实体的LLM上下文"""
        return self._world.agents_context.setdefault(
            entity.name, AgentContext(name=entity.name, context=[])
        )

    ###############################################################################################################################################
    def remove_agent_context(self, entity: Entity) -> None:
        """从 agents_context 中移除实体的LLM上下文（若存在）"""
        if entity.name in self._world.agents_context:
            logger.debug(
                f"remove_agent_context: {entity.name} in agents_context, pop it"
            )
            self._world.agents_context.pop(entity.name, None)

    ###############################################################################################################################################
    def add_system_message(self, entity: Entity, system_message: SystemMessage) -> None:
        """添加系统消息到实体的LLM上下文，必须是第一条消息"""
        agent_context = self.get_agent_context(entity)
        assert (
            len(agent_context.context) == 0
        ), "system message should be the first message"
        agent_context.context.append(system_message)

    ###############################################################################################################################################
    def add_human_message(self, entity: Entity, human_message: HumanMessage) -> None:
        """添加用户消息到实体的LLM上下文"""
        agent_context = self.get_agent_context(entity)
        agent_context.context.append(human_message)

    ###############################################################################################################################################
    def add_ai_message(self, entity: Entity, ai_message: AIMessage) -> None:
        """添加AI响应消息到实体的LLM上下文"""
        assert ai_message.content != "", "ai_message content should not be empty"
        # 最后添加到上下文中。
        agent_context = self.get_agent_context(entity)
        agent_context.context.append(ai_message)

    ###############################################################################################################################################
    def filter_messages_by_attributes(
        self,
        entity: Entity,
        attributes: Dict[str, Any],
        reverse_order: bool = True,
    ) -> List[SystemMessage | HumanMessage | AIMessage | ToolMessage]:
        """根据属性字典过滤实体上下文中的消息

        Args:
            entity: 要查询的实体
            attributes: 要匹配的属性字典，所有键值对必须完全匹配（空字典匹配所有消息）
            reverse_order: 是否逆序遍历，默认True

        Returns:
            匹配的消息列表
        """
        found_messages: List[SystemMessage | HumanMessage | AIMessage | ToolMessage] = (
            []
        )
        context = self.get_agent_context(entity).context

        # 空字典不匹配任何消息
        if not attributes:
            return []

        # 进行查找
        for chat_message in reversed(context) if reverse_order else context:
            try:
                # 严格匹配：消息必须有所有指定的属性，且值必须匹配
                all_matched = True
                for attr_key, attr_value in attributes.items():
                    if not hasattr(chat_message, attr_key):
                        all_matched = False
                        break
                    if getattr(chat_message, attr_key) != attr_value:
                        all_matched = False
                        break

                if all_matched:
                    found_messages.append(chat_message)

            except Exception as e:
                logger.error(
                    f"filter_messages_by_attributes error for {entity.name}: {e}"
                )
                continue

        return found_messages

    #######################################################################################################################################
    def remove_messages(
        self,
        entity: Entity,
        messages: Sequence[BaseMessage],
    ) -> int:
        """从实体上下文中删除指定的消息对象

        Args:
            entity: 要操作的实体
            messages: 要删除的消息对象列表

        Returns:
            实际删除的消息数量
        """
        if len(messages) == 0:
            return 0

        context = self.get_agent_context(entity).context
        original_length = len(context)

        # 删除指定的消息对象
        context[:] = [msg for msg in context if msg not in messages]

        deleted_count = original_length - len(context)
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
        """从实体上下文中删除指定范围的消息（包含两端）

        Args:
            entity: 要操作的实体
            begin_message: 范围起始消息
            end_message: 范围结束消息

        Returns:
            被删除的消息列表
        """
        assert (
            begin_message != end_message
        ), "begin_message and end_message should not be the same"

        agent_context = self.get_agent_context(entity)
        begin_message_index = agent_context.context.index(begin_message)
        end_message_index = agent_context.context.index(end_message) + 1

        # 保存要删除的消息
        deleted_messages = agent_context.context[begin_message_index:end_message_index]

        # 开始移除！！！！。
        del agent_context.context[begin_message_index:end_message_index]
        logger.debug(f"remove_message_range= {entity.name}")
        logger.debug(f"begin_message: \n{begin_message.model_dump_json(indent=2)}")
        logger.debug(f"end_message: \n{end_message.model_dump_json(indent=2)}")

        return deleted_messages

    #######################################################################################################################################
