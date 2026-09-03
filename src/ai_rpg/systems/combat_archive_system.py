"""战斗归档系统。"""

from typing import Final, List, final

from loguru import logger
from overrides import override

from ..deepseek import DeepSeekClient, batch_chat
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.dbg_game import DBGGame
from ..utils import prompt_builder
from ..models import (
    AIMessage,
    HumanMessage,
    PartyMemberComponent,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)


#######################################################################################################################################
@prompt_builder
def _build_combat_summary_prompt(
    actor_name: str,
    stage_name: str,
    total_rounds: int,
    result_text: str,
) -> str:
    """返回用于生成第一人称战斗摘要的 LLM prompt。

    该摘要会替换战斗原始逐条记录，成为角色此后对这场战斗的唯一记忆，
    因此必须事实忠实、克制，避免文学化渲染与凭空补充。
    """
    return f"""# 任务：压缩本次战斗记忆

你是 {actor_name}。上方是你的战斗全程记录：你在 {stage_name} 经历了 {total_rounds} 回合战斗，最终结果为 {result_text}。

请把它压缩成一段第一人称的连续复盘，作为你此后对这场战斗的唯一记忆（原始逐条记录将被移除）。按「进入 → 过程 → 结果」的顺序：
- 进入：所在场景、我方成员与对手；
- 过程：仅保留关键行动与转折，省略逐回合出牌细节与伤害数字；
- 结果：伤亡情况，且必须与「{result_text}」一致，不得写作「战斗尚未结束」或编造记录之外的情节。

约束：只使用上方记录中已出现的信息；客观、克制、事实化，禁止感官修饰与文学化渲染；整段不分段不空行，不含 Markdown 标记，控制在 150 字以内，纯文本输出。"""


#######################################################################################################################################
@final
class CombatArchiveSystem(ExecuteProcessor):
    """战斗结束后执行记忆压缩与归档（可插拔，不承担战斗状态转换）。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """每帧检查战斗是否结束；未结束则立即返回，结束则触发归档（记忆压缩）流程。"""
        if not self._game.current_dungeon_combat_room.combat.is_combat_completed:
            # 不是本阶段就直接返回, 如果过了，要么胜利，要么失败。
            return

        assert (
            self._game.current_dungeon_combat_room.combat.is_won
            or self._game.current_dungeon_combat_room.combat.is_lost
        ), "战斗结果状态异常！"

        # 压缩总结战斗结果（仅负责记忆归档，战斗状态转换由 CombatPostCombatTransitionSystem 承担）。
        await self._archive_all_combat_records()

    #######################################################################################################################################
    def _create_combat_summary_client(self, combat_actor: Entity) -> DeepSeekClient:
        """为单个盟友创建配置好的 DeepSeekClient，用于生成战斗摘要。"""
        total_rounds = len(self._game.current_dungeon_combat_room.combat.rounds or [])

        combat_stage_entity = self._game.resolve_stage_entity(combat_actor)
        assert (
            combat_stage_entity is not None
        ), f"无法获取角色 {combat_actor.name} 所在的场景实体！"

        combat = self._game.current_dungeon_combat_room.combat
        result_text = (
            "撤退" if combat.retreated else ("胜利" if combat.is_won else "失败")
        )

        return DeepSeekClient(
            name=combat_actor.name,
            full_prompt=_build_combat_summary_prompt(
                combat_actor.name, combat_stage_entity.name, total_rounds, result_text
            ),
            messages=self._game.get_agent_memory(combat_actor).messages,
        )

    #######################################################################################################################################
    def _archive_actor_combat_record(self, chat_client: DeepSeekClient) -> None:
        """对单个角色完成记忆压缩并派发 CombatArchiveEvent。"""

        if chat_client.response_ai_message is None:
            logger.error(f"LLM 响应缺失，无法归档战斗记录！chat_client: {chat_client}")
            return

        processed_actor_entity = self._game.get_entity_by_name(chat_client.name)
        assert (
            processed_actor_entity is not None
        ), f"无法找到角色实体：{chat_client.name}"

        # 在这里做压缩！！先测试，可以不做。TODO。
        deleted_messages = self._extract_combat_message_range(processed_actor_entity)
        assert len(deleted_messages) >= 0, "压缩战斗消息历史时出错！"

        # 合成一个字符串缓冲区
        buffer_string = get_buffer_string(
            deleted_messages, ai_prefix=f"""AI({processed_actor_entity.name})"""
        )

        # 将原始消息内容附在事件上，供后续流程（如记忆存储）使用
        self._game.add_human_message(
            entity=processed_actor_entity,
            human_message=HumanMessage(content=chat_client.full_prompt),
        )

        # 将 LLM 生成的摘要写回角色记忆
        self._game.add_ai_message(
            processed_actor_entity,
            chat_client.response_ai_message.model_copy(
                update={"removed_messages_content": buffer_string}
            ),
        )

    #######################################################################################################################################
    async def _archive_all_combat_records(self) -> None:
        """并行为所有盟友生成 LLM 摘要，依次归档每位角色的战斗记录。"""

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "无法获取玩家实体！"

        # 获取当前场景实体
        current_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert current_stage_entity is not None, "无法获取当前场景实体！"

        # 获取场景上的队伍成员（包括存活和死亡的）
        ally_actors = list(
            self._game.get_actors_in_stage(
                player_entity, Matcher(all_of=[PartyMemberComponent])
            )
        )

        # 创建聊天客户端
        chat_clients = [
            self._create_combat_summary_client(actor) for actor in ally_actors
        ]

        # 语言服务
        await batch_chat(clients=chat_clients)

        # 处理所有响应
        for chat_client in chat_clients:
            self._archive_actor_combat_record(chat_client)

    #######################################################################################################################################
    def _extract_combat_message_range(
        self, entity: Entity
    ) -> List[SystemMessage | HumanMessage | AIMessage | ToolMessage]:
        """从角色记忆中移除本场战斗的所有消息并返回被移除的列表。"""
        # 获取当前的战斗实体。
        stage_entity = self._game.resolve_stage_entity(entity)
        assert stage_entity is not None, f"无法获取角色 {entity.name} 所在的场景实体！"

        # 获取最近的战斗消息。
        begin_messages = self._game.filter_messages(
            entity=entity,
            predicate=lambda msg, index, messages: (
                getattr(msg, "combat_initialization", None) == stage_entity.name
            ),
        )
        assert (
            len(begin_messages) == 1
        ), f"没有找到战斗开始消息！entity: {entity.name}, stage_entity: {stage_entity.name}"

        # 获取最近的战斗消息。
        end_messages = self._game.filter_messages(
            entity=entity,
            predicate=lambda msg, index, messages: (
                getattr(msg, "combat_outcome", None) == stage_entity.name
            ),
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
