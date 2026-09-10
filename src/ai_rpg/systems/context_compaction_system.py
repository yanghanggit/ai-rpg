"""上下文压缩系统。"""

from typing import Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import ExecuteProcessor
from ..game.dbg_game import DBGGame
from ..models import HumanMessage, get_buffer_string
from .context_compaction_prompt_builders import build_compaction_prompt


#######################################################################################################################################
@final
class ContextCompactionSystem(ExecuteProcessor):
    """当 agent 上下文占比超过阈值时，将其记忆压缩为一条第一人称摘要。

    可插拔：默认阈值 0.8，可在构造时传入自定义阈值。
    """

    def __init__(self, game: DBGGame, threshold: float = 0.8) -> None:
        self._game: Final[DBGGame] = game
        self._threshold: Final[float] = threshold

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        # 收集所有上下文占比超过阈值的 agent（须至少有一条非 system 消息可压缩）
        over_threshold = [
            memory
            for memory in self._game.get_all_agent_memories().values()
            if memory.context_usage_ratio > self._threshold and len(memory.messages) > 1
        ]

        if not over_threshold:
            return

        # 为每个超阈值 agent 创建压缩客户端（messages 传入当前完整记忆）
        chat_clients: List[DeepSeekClient] = [
            DeepSeekClient(
                name=memory.name,
                full_prompt=build_compaction_prompt(memory.name),
                messages=memory.messages,
            )
            for memory in over_threshold
        ]

        # 并发压缩
        await batch_chat(clients=chat_clients)

        # 逐 agent 写回摘要并重置上下文占比
        for chat_client in chat_clients:
            summary = chat_client.response_content.strip()
            if not summary:
                logger.warning(
                    f"ContextCompactionSystem: 压缩摘要为空，name={chat_client.name}"
                )
                continue

            entity = self._game.get_entity_by_name(chat_client.name)
            assert entity is not None, f"无法找到实体：{chat_client.name}"

            # 提取被压缩的原始历史为整字符串，附在摘要消息上留痕
            agent_memory = self._game.get_agent_memory(entity)
            removed_buffer = get_buffer_string(agent_memory.messages[1:])

            self._game.compact_agent_memory(
                entity,
                HumanMessage(
                    content=summary,
                    removed_messages_content=removed_buffer,
                ),
            )
            logger.debug(f"ContextCompactionSystem: 已压缩 {chat_client.name} 的记忆")
