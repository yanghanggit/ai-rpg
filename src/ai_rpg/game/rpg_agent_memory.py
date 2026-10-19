from typing import Any, Callable, Dict, Final, List, Optional, Sequence

from loguru import logger

from ..entitas import Entity
from ..models import (
    AgentMemory,
    AIMessage,
    ChatMessage,
    HumanMessage,
    MessageSpan,
    SystemMessage,
    WorldState,
    find_marked_span,
    find_message,
)

MessagePredicate = Callable[[ChatMessage, int, Sequence[ChatMessage]], bool]

# replace_span 压缩时，把被替换掉的整段 dump 到新消息的额外属性所用的约定名。
REPLACED_MESSAGES_ATTR: Final[str] = "replaced_messages"

# 带此标记的消息在记忆压缩时必须原样保留（如「本次结算未完成」的系统说明）：
# 失败是需要长期留在上下文里的事实，不应被摘要抹平。
KEEP_ON_COMPACT_ATTR: Final[str] = "keep_on_compact"


#################################################################################################################################################
def _dump_messages(
    messages: Sequence[ChatMessage], dump_attr: str
) -> List[Dict[str, Any]]:
    """把一段消息 dump 成 JSON 原生 dict 列表。

    剔除每条消息上同名的 ``dump_attr``（若有），避免「总结套总结」时复盘 dump 层层嵌套、
    体量指数膨胀；被剔除的旧 dump 仍可在更早的存档快照中回溯。
    """
    dumped: List[Dict[str, Any]] = []
    for msg in messages:
        data = msg.model_dump(mode="json")
        data.pop(dump_attr, None)
        dumped.append(data)
    return dumped


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
    def get_all_agent_memories(self) -> Dict[str, AgentMemory]:
        """返回所有 agent 的 LLM 记忆（名称 → AgentMemory）。"""
        return self._world.agent_memories

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
        # 同步最新一次 LLM 调用的上下文占比到 AgentMemory（若消息携带该信息）
        self._sync_context_usage_ratio(agent_memory, ai_message)
        agent_memory.messages.append(ai_message)

    ###############################################################################################################################################
    def _sync_context_usage_ratio(
        self, agent_memory: AgentMemory, ai_message: AIMessage
    ) -> None:
        """若 AI 消息携带上下文占比，则同步到 AgentMemory。"""
        context_usage_ratio = getattr(ai_message, "context_usage_ratio", None)
        if context_usage_ratio is not None:
            agent_memory.context_usage_ratio = context_usage_ratio

    ###############################################################################################################################################
    def sync_latest_context_usage_ratio(self, entity: Entity) -> None:
        """从记忆中最新的 AI 消息同步上下文占比到 AgentMemory。

        供绕过 add_ai_message 直接追加 AI 消息的路径使用（如 agent_loop 工具调用循环）。
        """
        agent_memory = self.get_agent_memory(entity)
        ai_message = find_message(
            agent_memory.messages, lambda m: isinstance(m, AIMessage), reverse=True
        )
        if isinstance(ai_message, AIMessage):
            self._sync_context_usage_ratio(agent_memory, ai_message)

    ###############################################################################################################################################
    def reset_agent_memory(
        self,
        entity: Entity,
        new_messages: Sequence[ChatMessage] = (),
    ) -> None:
        """把实体记忆重制为「首条 system prompt + new_messages」，其余全部丢弃。

        这是记忆重制的唯一原语，语义就是「把记忆换成另一批消息」：
        - 默认 `new_messages=()`：等价于 `del messages[1:]`，仅保留首条 system prompt；
        - 传入 `[human_message]`：以该消息（如压缩摘要）作为新的记忆内容。

        ⚠️ 危险操作：原有 messages[1:] 会被不可逆丢弃，调用前请确认已落盘/留痕。
        仅在实体完成一次性任务、准备以全新状态复用其 persona 时调用
        （如副本导演归档后、副本生成系统组装完成后）。
        """
        agent_memory = self.get_agent_memory(entity)
        assert len(agent_memory.messages) > 0 and isinstance(
            agent_memory.messages[0], SystemMessage
        ), f"reset_agent_memory 要求实体 {entity.name!r} 首条消息必须是 SystemMessage"

        removed_count = len(agent_memory.messages) - 1
        agent_memory.messages[1:] = list(new_messages)
        agent_memory.context_usage_ratio = 0.0

        logger.info(
            f"[reset_agent_memory] ⚠️ 危险操作：已重制 {entity.name!r} 的 agent memory，"
            f"丢弃 {removed_count} 条旧消息，写入 {len(new_messages)} 条新消息"
            f"（保留首条 system prompt）"
        )

    ###############################################################################################################################################
    def compact_agent_memory(self, entity: Entity, human_message: HumanMessage) -> None:
        """将 agent 记忆中除首条 system 消息外的全部消息压缩为一条摘要，并重置上下文占比。

        human_message 由调用方构造，content 为摘要，可附加原始历史字符串留痕。
        本质是 reset_agent_memory 的一种用法：以「摘要 + 带 ``KEEP_ON_COMPACT_ATTR`` 的消息」重制记忆。
        """
        messages = self.get_agent_memory(entity).messages
        preserved = [m for m in messages[1:] if getattr(m, KEEP_ON_COMPACT_ATTR, False)]
        self.reset_agent_memory(entity, [human_message, *preserved])

    ###############################################################################################################################################
    def find_marked_span(
        self,
        entity: Entity,
        start_attr: str,
        value: Any,
        *,
        end_attr: Optional[str] = None,
    ) -> Optional[MessageSpan[ChatMessage]]:
        """按标记属性在实体记忆中定位一段连续消息（起终点，闭区间）。

        对 ``models.messages.find_marked_span`` 的实体级封装，供上层按自定义标记反查
        消息区间（例如 agent_loop 的 ``loop_id`` / ``loop_id_end``）。
        """
        return find_marked_span(
            self.get_agent_memory(entity).messages,
            start_attr,
            value,
            end_attr=end_attr,
        )

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
        messages: Sequence[ChatMessage],
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
        begin_message: ChatMessage,
        end_message: ChatMessage,
    ) -> List[ChatMessage]:
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
    def replace_span(
        self,
        entity: Entity,
        start_index: int,
        end_index: int,
        new_messages: Sequence[ChatMessage],
        *,
        dump_attr: Optional[str] = None,
    ) -> List[ChatMessage]:
        """用 new_messages 替换记忆中 ``[start_index, end_index)`` 半开区间，返回被替换的消息。

        与 ``AgentLoopResult.start_index / end_index`` 同约定（左闭右开），供「把一次
        loop 的整段过程压缩成一条总结」这类针对性压缩使用。传空 new_messages 即为回滚删除。

        ``dump_attr`` 非空时，把被替换掉的整段（``model_dump(mode="json")`` 的结构化
        列表，见 ``_dump_messages``）作为额外属性外挂到**最后一条新消息**上，供事后复盘。
        额外属性不进 LLM payload，故不增加上下文开销；``new_messages`` 为空（回滚）时
        无处挂载，自动跳过。
        """
        agent_memory = self.get_agent_memory(entity)
        replaced = agent_memory.messages[start_index:end_index]
        new_list = list(new_messages)
        agent_memory.messages[start_index:end_index] = new_list
        attach_dump = dump_attr is not None and len(new_list) > 0
        if dump_attr is not None and len(new_list) > 0:
            setattr(new_list[-1], dump_attr, _dump_messages(replaced, dump_attr))
        logger.debug(
            f"replace_span: {entity.name} 用 {len(new_list)} 条替换 "
            f"[{start_index}:{end_index}) 的 {len(replaced)} 条消息"
            + (f"（dump→{dump_attr}）" if attach_dump else "")
        )
        return replaced

    #######################################################################################################################################
    def insert_messages(
        self,
        entity: Entity,
        index: int,
        messages: Sequence[ChatMessage],
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
