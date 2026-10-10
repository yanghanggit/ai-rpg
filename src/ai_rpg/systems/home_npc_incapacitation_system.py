"""家园 NPC 失能系统。"""

from typing import Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..models import (
    ActorComponent,
    CharacterStatsComponent,
    HumanMessage,
    IncapacitatedComponent,
    NPCComponent,
    PartyRosterComponent,
    PlayerComponent,
    get_buffer_string,
)
from .context_compaction_prompt_builders import build_compaction_prompt


#######################################################################################################################################
@final
class HomeNpcIncapacitationSystem(ExecuteProcessor):
    """检查家园 NPC 的 lives，耗尽则压缩记忆并标记为永久失能。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ####################################################################################################################################
    @override
    async def execute(self) -> None:
        # 收集 lives 已耗尽、尚未失能、且当前在家园场景的 NPC（排除玩家）
        exhausted: List[Entity] = []
        for entity in self._game.get_group(
            Matcher(
                all_of=[ActorComponent, NPCComponent, CharacterStatsComponent],
                none_of=[PlayerComponent, IncapacitatedComponent],
            )
        ).entities:
            if not self._game.is_actor_in_home_stage(entity):
                continue
            if entity.get(CharacterStatsComponent).stats.lives > 0:
                continue
            exhausted.append(entity)

        if not exhausted:
            return

        # 先压缩记忆：仅在仍有可压缩内容（除首条 system 外还有消息）时发起 LLM 压缩
        chat_clients: List[DeepSeekClient] = []
        for entity in exhausted:
            memory = self._game.get_agent_memory(entity)
            if len(memory.messages) <= 1:
                logger.debug(
                    f"HomeNpcIncapacitationSystem: {entity.name} 无可压缩内容，跳过压缩"
                )
                continue
            chat_clients.append(
                DeepSeekClient(
                    name=memory.name,
                    prompt=build_compaction_prompt(memory.name),
                    messages=memory.messages,
                )
            )

        if chat_clients:

            # 批量发送压缩请求给 LLM，并等待所有响应完成
            await batch_chat(clients=chat_clients)

            # 处理每个 LLM 压缩响应，更新对应 NPC 的记忆
            for chat_client in chat_clients:
                summary = chat_client.response_content.strip()
                if not summary:
                    logger.warning(
                        f"HomeNpcIncapacitationSystem: 压缩摘要为空，name={chat_client.name}"
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
                    f"HomeNpcIncapacitationSystem: 已压缩 {chat_client.name} 的记忆"
                )

        # 再统一标记失能，避免后续周期重复触发（压缩失败也照常失能）
        for entity in exhausted:
            logger.info(
                f"HomeNpcIncapacitationSystem: {entity.name} lives 已耗尽，标记为永久失能"
            )
            entity.replace(IncapacitatedComponent, entity.name)

            # 将失能角色从玩家队伍名单中移除
            self._remove_from_party_roster(entity.name)

    ####################################################################################################################################
    def _remove_from_party_roster(self, member_name: str) -> None:
        """将失能角色从玩家队伍名单中移除（已永久失能者无法再进入副本）。"""
        player_entity = self._game.get_player_entity()
        if player_entity is None or not player_entity.has(PartyRosterComponent):
            return

        roster = player_entity.get(PartyRosterComponent)
        if member_name not in roster.members:
            return

        # 生成新的队伍成员列表，排除已失能的角色
        new_members = [m for m in roster.members if m != member_name]
        if new_members:
            player_entity.replace(PartyRosterComponent, player_entity.name, new_members)
        else:
            player_entity.remove(PartyRosterComponent)

        # 记录已将失能角色移出队伍名单的操作
        logger.info(
            f"HomeNpcIncapacitationSystem: 已将失能角色 {member_name} 移出队伍名单"
        )


#######################################################################################################################################
