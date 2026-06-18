"""战斗归档系统。

战斗结束后为每位盟友并行生成第一人称战斗摘要（LLM），
将战斗期间的详细消息从角色上下文中移除并替换为压缩摘要，
"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    CombatArchiveEvent,
    PartyMemberComponent,
    get_buffer_string,
)


#######################################################################################################################################
def _generate_combat_summary_prompt(
    actor_name: str, stage_name: str, total_rounds: int
) -> str:
    """返回用于生成第一人称战斗摘要的 LLM prompt。

    Args:
        actor_name: 保留参数，暂未注入 prompt
        stage_name: 战斗场景名称
        total_rounds: 本场战斗总回合数
    """
    return f"""# 战斗已结束，记忆归档，并以纯文本方式输出。

你在 {stage_name} 经历了 {total_rounds} 回合战斗，现在将整场战斗压缩为简要回忆录。

**用第一人称叙述战斗摘要**：起因（对手是谁、我方是谁）、关键经过（战术、配合、转折）、结局（胜负、收获）。只记录关键要素，去除无关细节。

**禁止JSON格式、代码块、大括号、键值对**，这是回忆日记，不是数据分析。请纯文本方式返回。"""


#######################################################################################################################################
def _format_combat_archive_message(
    actor_name: str, stage_name: str, combat_experience: str
) -> str:
    """将 LLM 生成的战斗摘要包装为写入角色上下文的通知消息。

    Args:
        actor_name: 保留参数，暂未注入消息
        stage_name: 战斗场景名称
        combat_experience: LLM 生成的战斗摘要文本
    """
    return f"""# 你在 {stage_name} 的战斗已结束

{combat_experience}

这段经历已记录。"""


#######################################################################################################################################
@final
class CombatArchiveSystem(ExecuteProcessor):
    """战斗结束后执行上下文压缩与事件派发。"""

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """每帧检查战斗是否结束；未结束则立即返回，结束则触发归档流程。"""
        if not self._game.current_dungeon.is_combat_completed:
            # 不是本阶段就直接返回, 如果过了，要么胜利，要么失败。
            return

        assert (
            self._game.current_dungeon.is_won or self._game.current_dungeon.is_lost
        ), "战斗结果状态异常！"

        # 压缩总结战斗结果。
        await self._archive_all_combat_records()

        # 标记战斗已归档，触发后续流程（如记忆存储、场景过渡等）
        self._game.current_dungeon.transition_to_post_combat()

    #######################################################################################################################################
    def _create_combat_summary_clients(
        self, combat_actors: List[Entity]
    ) -> List[DeepSeekClient]:
        """为每位盟友创建配置好的 DeepSeekClient，用于并行生成战斗摘要。

        Args:
            combat_actors: 参与战斗的盟友实体列表

        Returns:
            与 combat_actors 一一对应的 DeepSeekClient 列表
        """
        chat_clients: List[DeepSeekClient] = []

        # 获取总回合数
        total_rounds = len(self._game.current_dungeon.current_rounds or [])

        for combat_actor in combat_actors:

            combat_stage_entity = self._game.resolve_stage_entity(combat_actor)
            assert (
                combat_stage_entity is not None
            ), f"无法获取角色 {combat_actor.name} 所在的场景实体！"

            # 生成请求处理器
            chat_clients.append(
                DeepSeekClient(
                    name=combat_actor.name,
                    prompt=_generate_combat_summary_prompt(
                        combat_actor.name, combat_stage_entity.name, total_rounds
                    ),
                    context=self._game.get_agent_context(combat_actor).context,
                )
            )

        return chat_clients

    #######################################################################################################################################
    def _archive_actor_combat_record(self, chat_client: DeepSeekClient) -> None:
        """对单个角色完成上下文压缩并派发 CombatArchiveEvent。

        从角色上下文移除战斗详细消息，将 LLM 生成的摘要写回上下文，
        并将被移除的原始消息序列化为字符串附在事件上。

        Args:
            chat_client: 已完成 LLM 调用的客户端，name 对应角色实体名
        """
        processed_actor_entity = self._game.get_entity_by_name(chat_client.name)
        assert (
            processed_actor_entity is not None
        ), f"无法找到角色实体：{chat_client.name}"

        combat_stage_entity = self._game.resolve_stage_entity(processed_actor_entity)
        assert (
            combat_stage_entity is not None
        ), f"无法获取角色 {processed_actor_entity.name} 所在的场景实体！"

        # 在这里做压缩！！先测试，可以不做。TODO。
        deleted_messages = self._extract_combat_message_range(processed_actor_entity)
        assert len(deleted_messages) >= 0, "压缩战斗消息历史时出错！"

        # 压缩后的战斗经历，就是战斗过程做成摘要。
        combat_summary = _format_combat_archive_message(
            processed_actor_entity.name,
            combat_stage_entity.name,
            chat_client.response_content,
        )

        # 合成一个字符串缓冲区
        buffer_string = get_buffer_string(
            deleted_messages, ai_prefix=f"""AI({processed_actor_entity.name})"""
        )

        # 添加记忆，并给客户端。
        self._game.notify_entities(
            set({processed_actor_entity}),
            CombatArchiveEvent(
                message=combat_summary,
                actor=processed_actor_entity.name,
                summary=chat_client.response_content,
            ),
            removed_messages_content=buffer_string,
        )

    #######################################################################################################################################
    async def _archive_all_combat_records(self) -> None:
        """并行为所有盟友生成 LLM 摘要，依次归档每位角色的战斗记录。"""

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法获取玩家实体！"

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None, "无法获取当前场景实体！"

        # 获取场景上的所有角色（包括存活和死亡的）
        actors_in_stage = self._game.get_actors_in_stage(player_entity)

        # 过滤出远征队成员
        ally_actors = [
            actor for actor in actors_in_stage if actor.has(PartyMemberComponent)
        ]

        # 创建聊天客户端
        chat_clients = self._create_combat_summary_clients(list(ally_actors))

        # 语言服务
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 处理所有响应
        for chat_client in chat_clients:
            self._archive_actor_combat_record(chat_client)

    #######################################################################################################################################
    def _extract_combat_message_range(
        self, entity: Entity
    ) -> List[SystemMessage | HumanMessage | AIMessage | ToolMessage]:
        """从角色上下文中移除本场战斗的所有消息并返回被移除的列表。

        以 combat_initialization 和 combat_outcome 属性标记的消息作为边界定位范围。

        Args:
            entity: 要压缩上下文的角色实体

        Returns:
            被移除的消息列表；标记消息缺失时 assert 失败
        """
        # 获取当前的战斗实体。
        stage_entity = self._game.resolve_stage_entity(entity)
        assert stage_entity is not None, f"无法获取角色 {entity.name} 所在的场景实体！"

        # 获取最近的战斗消息。
        begin_messages = self._game.filter_messages_by_attributes(
            entity=entity,
            attributes={"combat_initialization": stage_entity.name},
        )
        assert (
            len(begin_messages) == 1
        ), f"没有找到战斗开始消息！entity: {entity.name}, stage_entity: {stage_entity.name}"

        # 获取最近的战斗消息。
        end_messages = self._game.filter_messages_by_attributes(
            entity=entity,
            attributes={"combat_outcome": stage_entity.name},
        )
        assert (
            len(end_messages) == 1
        ), f"没有找到战斗结束消息！entity: {entity.name}, stage_entity: {stage_entity.name}"

        # 必须同时有开始和结束消息。
        if not begin_messages or not end_messages:
            logger.error(
                f"战斗消息不完整！{entity.name} begin_message: {begin_messages} end_message: {end_messages}"
            )
            return []

        # 压缩战斗消息。
        return self._game.remove_message_range(
            entity, begin_messages[0], end_messages[0]
        )

    #######################################################################################################################################
