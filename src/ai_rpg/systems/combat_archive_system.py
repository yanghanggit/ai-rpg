"""战斗归档系统。"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, ExecuteProcessor
from ..game.dbg_game import DBGGame
from ..models import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    PartyMemberComponent,
    get_buffer_string,
)


#######################################################################################################################################
def _generate_combat_summary_prompt(stage_name: str, total_rounds: int) -> str:
    """返回用于生成第一人称战斗摘要的 LLM prompt。"""
    return f"""# 战斗结束，归档这段记忆。

你在 {stage_name} 完成了 {total_rounds} 回合的战斗。
以第一人称写一段连续的战斗复盘，按顺序写明：进入（场景、我方成员、对手）、过程（关键行动与转折）、结果（胜利/撤退/失败，伤亡情况）。
要求：客观简洁，不用修辞，整段不分段不空行，纯文本输出。"""


#######################################################################################################################################
@final
class CombatArchiveSystem(ExecuteProcessor):
    """战斗结束后执行上下文压缩与事件派发。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """每帧检查战斗是否结束；未结束则立即返回，结束则触发归档流程。"""
        if not self._game.current_combat_room.combat.is_combat_completed:
            # 不是本阶段就直接返回, 如果过了，要么胜利，要么失败。
            return

        assert (
            self._game.current_combat_room.combat.is_won
            or self._game.current_combat_room.combat.is_lost
        ), "战斗结果状态异常！"

        # 压缩总结战斗结果。
        await self._archive_all_combat_records()

        # 标记战斗已归档，触发后续流程（如记忆存储、场景过渡等）
        self._game.current_combat_room.combat.transition_to_post_combat()

    #######################################################################################################################################
    def _create_combat_summary_client(self, combat_actor: Entity) -> DeepSeekClient:
        """为单个盟友创建配置好的 DeepSeekClient，用于生成战斗摘要。"""
        total_rounds = len(self._game.current_combat_room.combat.rounds or [])

        combat_stage_entity = self._game.resolve_stage_entity(combat_actor)
        assert (
            combat_stage_entity is not None
        ), f"无法获取角色 {combat_actor.name} 所在的场景实体！"

        return DeepSeekClient(
            name=combat_actor.name,
            prompt=_generate_combat_summary_prompt(
                combat_stage_entity.name, total_rounds
            ),
            context=self._game.get_agent_context(combat_actor).context,
        )

    #######################################################################################################################################
    def _archive_actor_combat_record(self, chat_client: DeepSeekClient) -> None:
        """对单个角色完成上下文压缩并派发 CombatArchiveEvent。"""

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

        # 移除战斗初始化阶段插入的战斗专用规则 system message（[1]），战斗结束后不再生效
        self._remove_combat_system_rules_message(processed_actor_entity)

        # 合成一个字符串缓冲区
        buffer_string = get_buffer_string(
            deleted_messages, ai_prefix=f"""AI({processed_actor_entity.name})"""
        )

        # 将原始消息内容附在事件上，供后续流程（如记忆存储）使用
        self._game.add_human_message(
            entity=processed_actor_entity,
            human_message=HumanMessage(content=chat_client.prompt),
        )

        # 将 LLM 生成的摘要写回角色上下文
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

        # 获取场景上的所有角色（包括存活和死亡的）
        actors_in_stage = self._game.get_actors_in_stage(player_entity)

        # 过滤出远征队成员
        ally_actors = [
            actor for actor in actors_in_stage if actor.has(PartyMemberComponent)
        ]

        # 创建聊天客户端
        chat_clients = [
            self._create_combat_summary_client(actor) for actor in ally_actors
        ]

        # 语言服务
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 处理所有响应
        for chat_client in chat_clients:
            self._archive_actor_combat_record(chat_client)

    #######################################################################################################################################
    def _extract_combat_message_range(
        self, entity: Entity
    ) -> List[SystemMessage | HumanMessage | AIMessage | ToolMessage]:
        """从角色上下文中移除本场战斗的所有消息并返回被移除的列表。"""
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
    def _remove_combat_system_rules_message(self, entity: Entity) -> None:
        """移除战斗初始化阶段插入的战斗专用规则 system message（以 combat_system_rules 属性标记定位）。"""
        combat_system_rules_messages = self._game.filter_messages_by_attributes(
            entity=entity,
            attributes={"combat_system_rules": entity.name},
        )
        if not combat_system_rules_messages:
            logger.warning(
                f"[{entity.name}] 未找到战斗专用规则 system message，跳过移除!"
            )
            return

        removed_count = self._game.remove_messages(entity, combat_system_rules_messages)
        logger.debug(
            f"[{entity.name}] 已移除 {removed_count} 条战斗专用规则 system message"
        )

    #######################################################################################################################################
