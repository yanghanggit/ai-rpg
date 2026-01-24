from typing import Final, List, final
from loguru import logger
from overrides import override
from ..chat_service.client import ChatClient
from ..entitas import Entity, ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    CombatArchiveEvent,
    AllyComponent,
)
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    get_buffer_string,
)


#######################################################################################################################################
def _generate_combat_summary_prompt(
    actor_name: str, stage_name: str, total_rounds: int
) -> str:
    """生成战斗总结的AI提示词。

    为角色生成一个用于生成战斗经历总结的prompt，指导角色用第一人称视角
    简要描述战斗场景、对手、过程、结果和感受。要求单段紧凑叙述，
    不超过150字。

    Args:
        actor_name: 角色名称（未直接使用，保留以便未来扩展）
        stage_name: 战斗发生的场景名称
        total_rounds: 战斗总回合数

    Returns:
        格式化的AI提示词字符串
    """
    return f"""# 指令！战斗已结束，记忆归档，并以纯文本方式输出。

你在 {stage_name} 经历了 {total_rounds} 回合战斗，现在将整场战斗压缩为简要回忆录。

**用第一人称叙述战斗摘要**：起因（对手是谁、我方是谁）、关键经过（战术、配合、转折）、结局（胜负、收获）。只记录关键要素，去除无关细节。

**禁止JSON格式、代码块、大括号、键值对**，这是回忆日记，不是数据分析。请纯文本方式返回。"""


#######################################################################################################################################
def _format_combat_archive_message(
    actor_name: str, stage_name: str, combat_experience: str
) -> str:
    """格式化战斗归档消息，用于发送给角色。

    将AI生成的战斗经历总结包装成一条完整的通知消息，
    告知角色战斗已结束且经历已被记录。这条消息会被添加到
    角色的上下文中。

    Args:
        actor_name: 角色名称（未直接使用，保留以便未来扩展）
        stage_name: 战斗发生的场景名称
        combat_experience: AI生成的战斗经历总结文本

    Returns:
        格式化后的归档消息字符串
    """
    return f""" 提示！你在 {stage_name} 的战斗已结束

{combat_experience}

这段经历已记录。"""


#######################################################################################################################################
def _get_combat_ally_actors(game: TCGGame) -> List[Entity]:
    """获取当前战斗场景中的所有盟友角色。

    通过玩家实体定位战斗场景，然后获取该场景上的所有盟友角色。
    包括存活和已死亡的盟友，因为他们都参与了战斗并需要记录经历。

    处理流程：
    1. 获取玩家实体（玩家所在场景即为战斗场景）
    2. 获取玩家所在的场景实体
    3. 获取该场景上的所有角色（使用get_actors_on_stage）
    4. 过滤出带有AllyComponent的角色

    Args:
        game: TCGGame游戏实例

    Returns:
        当前战斗场景中的所有盟友角色列表

    Raises:
        AssertionError: 当无法获取玩家实体或场景实体时
    """
    # 获取玩家实体，player在的场景就是战斗发生的场景
    player_entity = game.get_player_entity()
    assert player_entity is not None, "无法获取玩家实体！"

    # 获取当前场景实体
    current_stage_entity = game.resolve_stage_entity(player_entity)
    assert current_stage_entity is not None, "无法获取当前场景实体！"

    # 获取场景上的所有角色（包括存活和死亡的）
    actors_on_stage = game.get_actors_on_stage(player_entity)

    # 过滤出盟友角色
    ally_actors = [actor for actor in actors_on_stage if actor.has(AllyComponent)]

    return ally_actors


#######################################################################################################################################
@final
class CombatArchiveSystem(ExecuteProcessor):
    """战斗归档系统

    负责战斗结束后的记录归档工作：
    - 生成战斗总结：通过AI为每个角色生成第一人称战斗记录
    - 压缩历史消息：提取并删除战斗期间的详细消息，节省上下文空间
    - 归档记忆：将战斗经历触发CombatArchiveEvent，由记忆系统存入知识库
    """

    def __init__(self, game_context: TCGGame) -> None:
        self._game: Final[TCGGame] = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """执行战斗后处理流程。

        在每帧更新时被调用，检查战斗是否已完成。如果战斗完成：
        1. 验证战斗结果状态（必须为胜利或失败）
        2. 调用_archive_all_combat_records归档所有角色的战斗记录

        Note:
            - 如果战斗未完成，直接返回不做任何处理
            - 战斗完成后会触发AI总结生成、消息压缩和记忆归档
        """
        if not self._game.current_combat_sequence.is_completed:
            # 不是本阶段就直接返回, 如果过了，要么胜利，要么失败。
            return

        assert (
            self._game.current_combat_sequence.is_won
            or self._game.current_combat_sequence.is_lost
        ), "战斗结果状态异常！"

        # 压缩总结战斗结果。
        await self._archive_all_combat_records()

    #######################################################################################################################################
    def _create_combat_summary_clients(
        self, combat_actors: List[Entity]
    ) -> List[ChatClient]:
        """为所有战斗角色创建用于生成战斗总结的聊天客户端。

        为每个参战角色创建ChatClient实例，配置包含：
        - 角色名称
        - AI提示词（基于场景名称和战斗回合数）
        - 角色的当前上下文（包含战斗历史消息）

        Args:
            combat_actors: 参与战斗的角色实体列表

        Returns:
            ChatClient列表，每个客户端对应一个角色
        """
        chat_clients: List[ChatClient] = []

        # 获取总回合数
        total_rounds = len(self._game.current_combat_sequence.current_rounds)

        for combat_actor in combat_actors:

            combat_stage_entity = self._game.resolve_stage_entity(combat_actor)
            assert (
                combat_stage_entity is not None
            ), f"无法获取角色 {combat_actor.name} 所在的场景实体！"

            # 生成请求处理器
            chat_clients.append(
                ChatClient(
                    name=combat_actor.name,
                    prompt=_generate_combat_summary_prompt(
                        combat_actor.name, combat_stage_entity.name, total_rounds
                    ),
                    context=self._game.get_agent_context(combat_actor).context,
                )
            )

        return chat_clients

    #######################################################################################################################################
    def _archive_actor_combat_record(self, chat_client: ChatClient) -> None:
        """归档单个角色的战斗记录。

        处理流程：
        1. 通过角色名称获取角色实体和所在场景
        2. 调用_extract_combat_message_range提取并删除战斗期间的所有消息
        3. 使用_format_combat_archive_message格式化AI生成的战斗总结
        4. 将删除的消息转换为字符串缓冲区
        5. 通过notify_entities触发CombatCompleteEvent，传递总结消息和删除的历史

        Args:
            chat_client: 包含角色名称和AI生成的战斗总结的聊天客户端

        Note:
            - 删除的消息会作为removed_messages_content传递，用于后续的记忆归档
            - CombatArchiveEvent会触发记忆系统将战斗经历存入知识库
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
        """归档所有参战角色的战斗记录。

        执行完整的批量归档流程：
        1. 获取当前战斗场景中的所有盟友角色（通过玩家定位场景）
        2. 为每个角色创建ChatClient（包含总结prompt和上下文）
        3. 并行调用AI服务生成所有角色的战斗总结
        4. 遍历每个响应，调用_archive_actor_combat_record处理单个角色的归档

        Note:
            - 使用ChatClient.gather_request_post实现并行AI请求，提高效率
            - 仅处理当前战斗场景中的盟友角色，不包括敌人和其他场景的角色
            - 包括已死亡的盟友，因为他们也参与了战斗并需要记录经历
            - 每个角色的处理是独立的，互不影响
        """
        # 获取当前战斗场景中的所有盟友角色
        combat_actors = _get_combat_ally_actors(self._game)

        # 创建聊天客户端
        chat_clients = self._create_combat_summary_clients(list(combat_actors))

        # 语言服务
        await ChatClient.batch_chat(clients=chat_clients)

        # 处理所有响应
        for chat_client in chat_clients:
            self._archive_actor_combat_record(chat_client)

    #######################################################################################################################################
    def _extract_combat_message_range(
        self, entity: Entity
    ) -> List[SystemMessage | HumanMessage | AIMessage]:
        """提取并删除角色的战斗消息范围。

        通过查找战斗开始和结束的标记消息，提取期间的所有消息并从
        角色的聊天历史中移除。这些被移除的消息会被压缩并归档到记忆中。

        查找逻辑：
        1. 通过combat_initialization属性查找战斗开始消息
        2. 通过combat_outcome属性查找战斗结束消息
        3. 调用remove_message_range删除这两条消息之间的所有内容

        Args:
            entity: 需要处理的角色实体

        Returns:
            被删除的消息列表，包含SystemMessage、HumanMessage和AIMessage

        Raises:
            AssertionError: 当找不到开始或结束消息时

        Note:
            - 如果消息不完整，记录错误并返回空列表
            - 删除范围包括开始和结束消息之间的所有消息
        """
        # 获取当前的战斗实体。
        stage_entity = self._game.resolve_stage_entity(entity)
        assert stage_entity is not None

        # 获取最近的战斗消息。
        begin_messages = self._game.filter_human_messages_by_attribute(
            actor_entity=entity,
            attribute_key="combat_initialization",
            attribute_value=stage_entity.name,
        )
        assert (
            len(begin_messages) == 1
        ), f"没有找到战斗开始消息！entity: {entity.name}, stage_entity: {stage_entity.name}"

        # 获取最近的战斗消息。
        end_messages = self._game.filter_human_messages_by_attribute(
            actor_entity=entity,
            attribute_key="combat_outcome",
            attribute_value=stage_entity.name,
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
