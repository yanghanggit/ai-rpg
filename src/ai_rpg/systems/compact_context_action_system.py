"""手动上下文压缩动作系统。

由客户端（CLI/API）为指定实体挂载 CompactContextAction 后触发，
仅压缩该实体的记忆；与 ContextCompactionSystem（阈值兜底）互补。
"""

from typing import Dict, Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..models import CompactContextAction, HumanMessage, get_buffer_string
from .context_compaction_prompt_builders import build_compaction_prompt


#######################################################################################################################################
@final
class CompactContextActionSystem(ReactiveProcessor):
    """响应 CompactContextAction，压缩指定实体的记忆。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(CompactContextAction): GroupEvent.ADDED}

    #######################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(CompactContextAction)

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        # 仅保留存在可压缩内容（除首条 system 外还有消息）的实体
        chat_clients: List[DeepSeekClient] = []
        for entity in entities:
            memory = self._game.get_agent_memory(entity)
            if len(memory.messages) <= 1:
                logger.debug(
                    f"CompactContextActionSystem: {entity.name} 无可压缩内容，跳过"
                )
                continue

            chat_clients.append(
                DeepSeekClient(
                    name=memory.name,
                    full_prompt=build_compaction_prompt(memory.name),
                    messages=memory.messages,
                )
            )

        if not chat_clients:
            return

        # 并发压缩
        await batch_chat(clients=chat_clients)

        # 逐 agent 写回摘要并重置上下文占比
        for chat_client in chat_clients:
            summary = chat_client.response_content.strip()
            if not summary:
                logger.warning(
                    f"CompactContextActionSystem: 压缩摘要为空，name={chat_client.name}"
                )
                continue

            target_entity = self._game.get_entity_by_name(chat_client.name)
            assert target_entity is not None, f"无法找到实体：{chat_client.name}"

            # 提取被压缩的原始历史为整字符串，附在摘要消息上留痕
            agent_memory = self._game.get_agent_memory(target_entity)
            removed_buffer = get_buffer_string(agent_memory.messages[1:])

            self._game.compact_agent_memory(
                target_entity,
                HumanMessage(
                    content=summary,
                    removed_messages_content=removed_buffer,
                ),
            )
            logger.debug(
                f"CompactContextActionSystem: 已压缩 {chat_client.name} 的记忆"
            )

    #######################################################################################################################################
