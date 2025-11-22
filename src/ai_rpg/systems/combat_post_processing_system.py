"""战斗后处理系统

负责战斗结束后的清理和归档工作：
- 生成战斗总结：通过AI为每个角色生成第一人称战斗记录
- 压缩历史消息：将战斗期间的详细消息压缩成摘要，节省上下文空间
- 归档记忆：将战斗经历存入角色记忆，并触发战斗完成事件
"""

from typing import Final, List, final
from loguru import logger
from overrides import override
from ..chat_services.client import ChatClient
from ..entitas import Entity, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import (
    ActorComponent,
    CombatCompleteEvent,
    CombatResult,
    AllyComponent,
    CombatStatsComponent,
)


#######################################################################################################################################
def _generate_combat_summary_prompt(actor_name: str, stage_name: str) -> str:
    """生成战斗总结提示词"""
    return f"""# 指令！{actor_name} 在 {stage_name} 经历了一场战斗，现在需要用第一人称记录这次战斗经历。

请简要描述：
- 战斗场景和对手特征
- 战斗经过（开始、关键过程、结局）
- 你的状态与感受
- 同伴的表现（如有）

要求：单段紧凑叙述，不使用数字序号和多余空行，控制在150字以内。"""


#######################################################################################################################################
def _generate_combat_complete_summary(
    actor_name: str, stage_name: str, combat_experience: str
) -> str:
    """生成战斗完成总结"""
    return f""" 提示！{actor_name} 在 {stage_name} 的战斗已结束

{combat_experience}

这段经历已记录。"""


#######################################################################################################################################
@final
class CombatPostProcessingSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: Final[TCGGame] = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """执行战斗后处理流程：检查战斗是否完成，生成总结并进入后续阶段"""
        if not self._game.current_combat_sequence.is_completed:
            # 不是本阶段就直接返回, 如果过了，要么胜利，要么失败。
            return

        assert (
            self._game.current_combat_sequence.current_result == CombatResult.HERO_WIN
            or self._game.current_combat_sequence.current_result
            == CombatResult.HERO_LOSE
        ), "战斗结果状态异常！"

        # 压缩总结战斗结果。
        await self._generate_and_archive_combat_records()

        # 进入战斗后准备的状态，离开当前状态。
        self._game.current_combat_sequence.enter_post_combat_phase()

    #######################################################################################################################################
    def _create_combat_summary_clients(
        self, combat_actors: List[Entity]
    ) -> List[ChatClient]:
        """为所有战斗角色创建战斗总结的聊天客户端"""
        chat_clients: List[ChatClient] = []
        for combat_actor in combat_actors:

            combat_stage_entity = self._game.safe_get_stage_entity(combat_actor)
            assert (
                combat_stage_entity is not None
            ), f"无法获取角色 {combat_actor.name} 所在的场景实体！"

            # 生成请求处理器
            chat_clients.append(
                ChatClient(
                    name=combat_actor.name,
                    prompt=_generate_combat_summary_prompt(
                        combat_actor.name, combat_stage_entity.name
                    ),
                    context=self._game.get_agent_context(combat_actor).context,
                )
            )

        return chat_clients

    #######################################################################################################################################
    def _process_combat_summary_response(self, chat_client: ChatClient) -> None:
        """处理单个战斗总结响应：压缩历史、生成摘要、通知实体"""
        processed_actor_entity = self._game.get_entity_by_name(chat_client.name)
        assert processed_actor_entity is not None

        combat_stage_entity = self._game.safe_get_stage_entity(processed_actor_entity)
        assert combat_stage_entity is not None

        # 在这里做压缩！！先测试，可以不做。TODO。
        self._compress_combat_message_history(processed_actor_entity)

        # 压缩后的战斗经历，就是战斗过程做成摘要。
        combat_summary = _generate_combat_complete_summary(
            processed_actor_entity.name,
            combat_stage_entity.name,
            chat_client.response_content,
        )

        # 添加记忆，并给客户端。
        self._game.notify_entities(
            set({processed_actor_entity}),
            CombatCompleteEvent(
                message=combat_summary,
                actor=processed_actor_entity.name,
                summary=combat_summary,
            ),
        )

    #######################################################################################################################################
    async def _generate_and_archive_combat_records(self) -> None:
        """生成并归档战斗记录：为所有参战角色生成AI总结，压缩消息历史，触发完成事件"""
        # 获取所有需要进行角色规划的角色
        combat_actors = self._game.get_group(
            Matcher(
                all_of=[ActorComponent, AllyComponent, CombatStatsComponent],
            )
        ).entities

        # 创建聊天客户端
        chat_clients = self._create_combat_summary_clients(list(combat_actors))

        # 语言服务
        await ChatClient.gather_request_post(clients=chat_clients)

        # 处理所有响应
        for chat_client in chat_clients:
            self._process_combat_summary_response(chat_client)

    #######################################################################################################################################
    def _compress_combat_message_history(self, entity: Entity) -> None:
        """压缩角色的战斗消息历史：找到战斗开始和结束标记，将期间的详细消息压缩成摘要"""
        # 获取当前的战斗实体。
        stage_entity = self._game.safe_get_stage_entity(entity)
        assert stage_entity is not None

        # 获取最近的战斗消息。
        begin_messages = self._game.find_human_messages_by_attribute(
            actor_entity=entity,
            attribute_key="combat_kickoff",
            attribute_value=stage_entity.name,
        )
        assert (
            len(begin_messages) == 1
        ), f"没有找到战斗开始消息！entity: {entity.name}, stage_entity: {stage_entity.name}"

        # 获取最近的战斗消息。
        end_messages = self._game.find_human_messages_by_attribute(
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
            return

        # 压缩战斗消息。
        self._game.compress_combat_context(entity, begin_messages[0], end_messages[0])

    #######################################################################################################################################
