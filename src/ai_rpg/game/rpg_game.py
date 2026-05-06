from typing import Any, Dict, Final, List, Sequence, Set
from ..models.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from loguru import logger
from overrides import override
from ..entitas import Entity
from .game_session import GameSession
from .rpg_entity_manager import RPGEntityManager
from .rpg_game_pipeline_manager import RPGGamePipelineManager
from ..models import (
    AgentEventUnion,
    AgentContext,
    World,
)
from .player_session import PlayerSession


#################################################################################################################################################
class RPGGame(GameSession, RPGEntityManager, RPGGamePipelineManager):
    """
    RPG游戏核心类，基于ECS架构整合游戏会话管理、实体管理和LLM处理管道

    Attributes:
        player_session: 玩家会话对象
        world: 游戏世界对象，包含蓝图配置和运行时状态
    """

    def __init__(
        self,
        name: str,
        player_session: PlayerSession,
        world: World,
    ) -> None:

        # 必须按着此顺序实现父类
        GameSession.__init__(self, name)  # 需要传递 name
        RPGEntityManager.__init__(self)  # 继承 Context, 需要调用其 __init__
        RPGGamePipelineManager.__init__(self)  # 管道管理器初始化

        # 初始化player_session 和 world
        self._player_session: Final[PlayerSession] = player_session
        self._world: Final[World] = world

        # 验证玩家信息
        assert self._player_session.name != "", "玩家名字不能为空"
        assert self._player_session.actor != "", "玩家角色不能为空"

    ###############################################################################################################################################
    def get_agent_context(self, entity: Entity) -> AgentContext:
        """
        获取或创建实体的LLM上下文

        Args:
            entity: 要获取上下文的实体

        Returns:
            实体的上下文对象，若不存在则自动创建
        """
        return self._world.agents_context.setdefault(
            entity.name, AgentContext(name=entity.name, context=[])
        )

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体并清理其LLM上下文

        Args:
            entity: 要销毁的实体对象
        """
        logger.debug(f"destroy_entity: {entity.name}")
        if entity.name in self._world.agents_context:
            logger.debug(f"destroy_entity: {entity.name} in agents_context, pop it")
            self._world.agents_context.pop(entity.name, None)

        return super().destroy_entity(entity)

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        logger.debug("Exiting game, performing cleanup...")
        # 关闭所有管道
        self.shutdown_pipelines()

    ###############################################################################################################################################
    @override
    async def initialize(self) -> None:
        logger.debug("Initializing game, setting up pipelines and world state...")
        # 初始化所有管道
        await self.initialize_pipelines()

    ###############################################################################################################################################
    def restore_from_snapshot(self) -> "RPGGame":
        """从序列化数据中恢复游戏世界状态

        Returns:
            返回自身实例，支持链式调用
        """
        assert (
            len(self._world.entities_serialization) > 0
        ), "游戏中没有实体，不能恢复游戏"
        assert len(self._entities) == 0, "游戏中有实体，不能恢复游戏"
        if (len(self._world.entities_serialization) == 0) or (len(self._entities) > 0):
            logger.warning(
                f"游戏中没有实体，不能恢复游戏，entities_serialization = {self._world.entities_serialization}, entities = {self._entities}"
            )
            return self

        # 从序列化数据中恢复实体状态
        self.deserialize_entities(self._world.entities_serialization)
        return self

    ###############################################################################################################################################
    def flush_entities(self) -> "RPGGame":
        """保存当前游戏世界状态到持久化存储，并生成调试快照

        Returns:
            返回自身实例，支持链式调用
        """
        # 生成快照
        self._world.entities_serialization = self.serialize_entities(self._entities)
        return self

    ###############################################################################################################################################
    def add_system_message(self, entity: Entity, message_content: str) -> None:
        """添加系统消息到实体的LLM上下文，必须是第一条消息"""
        logger.info(
            f"add_system_message: {entity.name} 添加LLM system prompt:\n{message_content}"
        )
        agent_context = self.get_agent_context(entity)
        assert (
            len(agent_context.context) == 0
        ), "system message should be the first message"
        agent_context.context.append(SystemMessage(content=message_content))

    ###############################################################################################################################################
    def add_human_message(
        self, entity: Entity, message_content: str, **kwargs: Any
    ) -> None:
        """添加用户消息到实体的LLM上下文"""
        logger.debug(
            f"add_human_message: {entity.name} 添加LLM context:\n{message_content}"
        )
        if len(kwargs) > 0:
            # 如果 **kwargs 不是 空，就打印一下，这种消息比较特殊。
            logger.debug(f"kwargs: {kwargs}")

        agent_context = self.get_agent_context(entity)
        agent_context.context.extend([HumanMessage(content=message_content, **kwargs)])

    ###############################################################################################################################################
    def add_ai_message(
        self, entity: Entity, ai_message: AIMessage, **kwargs: Any
    ) -> None:
        """添加AI响应消息到实体的LLM上下文"""
        assert isinstance(ai_message, AIMessage)
        assert ai_message.content != "", "ai_message content should not be empty"
        if kwargs:
            for key, value in kwargs.items():
                setattr(ai_message, key, value)
        logger.debug(
            f"add_ai_message: {entity.name} 添加LLM context:\n{ai_message.content}"
        )
        agent_context = self.get_agent_context(entity)
        agent_context.context.append(ai_message)

    ###############################################################################################################################################
    def broadcast_to_stage(
        self,
        entity: Entity,
        agent_event: AgentEventUnion,
        exclude_entities: Set[Entity] = set(),
        **kwargs: Any,
    ) -> None:
        """向场景中的所有存活角色和场景实体广播事件

        Args:
            entity: 参考实体，用于确定目标场景
            agent_event: 要广播的事件消息
            exclude_entities: 要排除的实体集合
            **kwargs: 传递给HumanMessage的额外参数
        """
        stage_entity = self.resolve_stage_entity(entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
        if stage_entity is None:
            return

        need_broadcast_entities = self.get_actors_in_stage(stage_entity)
        need_broadcast_entities.add(stage_entity)

        if len(exclude_entities) > 0:
            need_broadcast_entities = need_broadcast_entities - exclude_entities

        self.notify_entities(need_broadcast_entities, agent_event, **kwargs)

    ###############################################################################################################################################
    def notify_entities(
        self,
        entities: Set[Entity],
        agent_event: AgentEventUnion,
        **kwargs: Any,
    ) -> None:
        """向指定实体集合发送通知，并同步到玩家客户端

        Args:
            entities: 要接收通知的实体集合
            agent_event: 要发送的事件消息
            **kwargs: 传递给HumanMessage的额外参数
        """
        # 正常的添加记忆。
        for entity in entities:
            self.add_human_message(entity, agent_event.message, **kwargs)

        # 最后都要发给客户端。
        self._player_session.add_agent_event_message(agent_event=agent_event)

    #######################################################################################################################################
    def filter_messages_by_attributes(
        self,
        entity: Entity,
        attributes: Dict[str, Any],
        reverse_order: bool = True,
    ) -> List[SystemMessage | HumanMessage | AIMessage]:
        """根据属性字典过滤实体上下文中的消息

        Args:
            entity: 要查询的实体
            attributes: 要匹配的属性字典，所有键值对必须完全匹配（空字典匹配所有消息）
            reverse_order: 是否逆序遍历，默认True

        Returns:
            匹配的消息列表
        """
        found_messages: List[SystemMessage | HumanMessage | AIMessage] = []
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
        begin_message: SystemMessage | HumanMessage | AIMessage,
        end_message: SystemMessage | HumanMessage | AIMessage,
    ) -> List[SystemMessage | HumanMessage | AIMessage]:
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
