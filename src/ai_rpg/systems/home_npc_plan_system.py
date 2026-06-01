from typing import Dict, Final, List, final
from ..models.messages import AIMessage
from loguru import logger
from overrides import override
from ..deepseek import DeepSeekClient
from ..entitas import Entity, Matcher, GroupEvent, ReactiveProcessor
from ..models import (
    StageDescriptionComponent,
    QueryAction,
    SpeakAction,
    WhisperAction,
    AnnounceAction,
    PlanAction,
    TransStageAction,
    HomeComponent,
    MindEvent,
    ActorComponent,
    NPCComponent,
    PlayerComponent,
    PlayerOnlyStageComponent,
)
from ..utils import extract_json_from_code_block
from ..game import TCGGame
from .home_planning_utils import (
    ActionPlanResponse,
    _build_action_planning_prompt,
    _build_compressed_planning_prompt,
    _format_mind_notification,
    is_player_active,
)


#######################################################################################################################################
@final
class HomeNpcPlanSystem(ReactiveProcessor):
    """家园 NPC 自主行动规划系统。

    响应式处理器，监听 PlanAction 组件触发，仅处理非玩家控制（无 PlayerComponent）的 NPC 实体。
    生成行动规划提示词，调用 LLM 获取决策，并转化为游戏行动组件。
    若玩家本轮有主动行动，NPC 进入待命模式（跳过 LLM 推理）。

    Attributes:
        _game: 游戏实例引用
        _use_compressed_prompt: 是否使用压缩 prompt 机制。
            True（默认）：对话历史存压缩版，full prompt 附挂在 home_actor_full_prompt 字段；
            False：与旧行为一致，对话历史直接存完整 prompt，不附挂额外字段。
    """

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(PlanAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlanAction)
            and entity.has(ActorComponent)
            and not entity.has(PlayerComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:

        # turn counter 由 HomePlayerContextSystem（注册在前）负责自增，此处直接读取。
        planning_turn = self._game._world.home_planning_turn_index

        # 若玩家本轮有主动行动，NPC 进入待命模式（跳过 LLM 推理）
        if is_player_active(self._game):
            for npc_entity in entities:
                self._inject_npc_standby_context(npc_entity, planning_turn)
            return

        # NPC：调用 LLM 进行行动规划
        chat_clients: List[DeepSeekClient] = self._create_actor_chat_clients(
            entities, planning_turn
        )
        await DeepSeekClient.batch_chat(clients=chat_clients)

        for chat_client in chat_clients:
            response_entity = self._game.get_entity_by_name(chat_client.name)
            assert (
                response_entity is not None
            ), f"Cannot find entity by name: {chat_client.name}"
            self._execute_actor_actions(response_entity, chat_client)

    #######################################################################################################################################
    def _inject_npc_standby_context(
        self, npc_entity: Entity, planning_turn_index: int
    ) -> None:
        """向 NPC 实体注入待命状态（跳过 LLM 推理）。

        玩家本轮有主动行动时，NPC 不进行推理，直接注入 passive_mind 并保持对话历史连贯。

        Args:
            npc_entity: NPC 实体
            planning_turn_index: 全局家园规划回合编号
        """
        current_stage = self._game.resolve_stage_entity(npc_entity)
        assert current_stage is not None

        other_actors_appearances = self._get_other_actors_appearances(
            npc_entity, current_stage
        )
        available_home_stages = self._get_available_home_stages(
            npc_entity, current_stage
        )

        stage_narrative = current_stage.get(StageDescriptionComponent).narrative
        available_stage_names = [e.name for e in available_home_stages]

        prompt = _build_action_planning_prompt(
            current_stage=current_stage.name,
            current_stage_narration=stage_narrative,
            other_actors_appearances=other_actors_appearances,
            available_home_stages=available_stage_names,
            planning_turn_index=planning_turn_index,
        )
        if self._use_compressed_prompt:
            compressed_prompt = _build_compressed_planning_prompt(
                current_stage=current_stage.name,
                current_stage_narration=stage_narrative,
                other_actors_appearances=other_actors_appearances,
                available_home_stages=available_stage_names,
                planning_turn_index=planning_turn_index,
            )
            self._game.add_human_message(
                npc_entity,
                compressed_prompt,
                home_actor_planning=npc_entity.name,
                home_actor_full_prompt=prompt,
            )
        else:
            self._game.add_human_message(
                npc_entity,
                prompt,
                home_actor_planning=npc_entity.name,
            )

        passive_mind = f"身处{current_stage.name}，待命。"
        standby_response = ActionPlanResponse(mind=passive_mind)
        self._game.add_ai_message(
            npc_entity,
            AIMessage(content=standby_response.model_dump_json(indent=2)),
        )

        self._game.notify_entities(
            {npc_entity},
            MindEvent(
                message=_format_mind_notification(npc_entity.name, passive_mind),
                actor=npc_entity.name,
                content=passive_mind,
            ),
        )

    #######################################################################################################################################
    def _execute_actor_actions(
        self, actor_entity: Entity, chat_client: DeepSeekClient
    ) -> None:
        """执行角色的行动决策。

        解析 AI 响应并转化为游戏行动组件，保存对话历史。

        Args:
            actor_entity: 角色实体
            chat_client: 聊天客户端（包含 AI 响应）
        """
        try:

            # 验证响应
            validated_response = ActionPlanResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )

            # 添加上下文！存入压缩版 prompt，附挂原始全量 prompt 供检索
            if self._use_compressed_prompt:
                self._game.add_human_message(
                    actor_entity,
                    chat_client.compressed_prompt,
                    home_actor_planning=actor_entity.name,
                    home_actor_full_prompt=chat_client.prompt,
                )
            else:
                self._game.add_human_message(
                    actor_entity,
                    chat_client.prompt,
                    home_actor_planning=actor_entity.name,
                )
            assert chat_client.response_ai_message is not None
            self._game.add_ai_message(actor_entity, chat_client.response_ai_message)

            # 添加内心独白: 上下文！，这里做直接添加与通知处理
            if validated_response.mind != "":

                self._game.notify_entities(
                    set({actor_entity}),
                    MindEvent(
                        message=_format_mind_notification(
                            actor_entity.name, validated_response.mind
                        ),
                        actor=actor_entity.name,
                        content=validated_response.mind,
                    ),
                )

            # 添加说话动作
            if len(validated_response.speak) > 0:
                actor_entity.replace(
                    SpeakAction, actor_entity.name, validated_response.speak
                )

            # 添加耳语动作
            if len(validated_response.whisper) > 0:
                actor_entity.replace(
                    WhisperAction, actor_entity.name, validated_response.whisper
                )

            # 添加宣布动作
            if validated_response.announce != "":
                actor_entity.replace(
                    AnnounceAction,
                    actor_entity.name,
                    validated_response.announce,
                )

            # 添加查询动作
            if validated_response.query != "":
                actor_entity.replace(
                    QueryAction, actor_entity.name, validated_response.query
                )

            # 最后：如果需要可以添加传送场景。
            if validated_response.trans_stage != "":
                actor_entity.replace(
                    TransStageAction,
                    actor_entity.name,
                    validated_response.trans_stage,
                )

        except Exception as e:
            logger.error(f"Exception: {e}")

    #######################################################################################################################################
    def _get_other_actors_appearances(
        self, actor_entity: Entity, current_stage: Entity
    ) -> Dict[str, str]:
        """获取当前场景内除自身以外的所有角色外观描述。

        Args:
            actor_entity: 当前角色实体（将被排除）
            current_stage: 当前所在场景实体

        Returns:
            其他角色的外观描述（角色名 -> 外观）
        """
        appearances = self._game.get_actor_appearances_in_stage(current_stage)
        appearances.pop(actor_entity.name, None)
        return appearances

    #######################################################################################################################################
    def _get_available_home_stages(
        self, actor_entity: Entity, current_stage: Entity
    ) -> set[Entity]:
        """获取角色可前往的家园场景集合。

        玩家可前往所有家园场景；非玩家只能前往不含 PlayerOnlyStageComponent 的场景。
        均排除当前所在场景。

        Args:
            actor_entity: 角色实体
            current_stage: 当前所在场景实体

        Returns:
            可前往的家园场景实体集合
        """
        home_stage_entities = self._game.get_group(
            Matcher(all_of=[HomeComponent])
        ).entities.copy()
        home_stage_entities.discard(current_stage)

        if actor_entity.has(PlayerComponent):
            return home_stage_entities

        return {
            stage
            for stage in home_stage_entities
            if not stage.has(PlayerOnlyStageComponent)
        }

    #######################################################################################################################################
    def _create_actor_chat_clients(
        self, actor_entities: List[Entity], planning_turn_index: int
    ) -> List[DeepSeekClient]:
        """为角色创建聊天客户端。

        收集场景上下文并生成提示词，创建聊天客户端。

        Args:
            actor_entities: 角色实体列表
            planning_turn_index: 全局家园规划回合编号

        Returns:
            聊天客户端列表
        """
        chat_clients: List[DeepSeekClient] = []

        for actor_entity in actor_entities:

            # 找到当前场景
            current_stage = self._game.resolve_stage_entity(actor_entity)
            assert current_stage is not None

            # 找到当前场景内所有角色 & 他们的外观描述（不含自己）
            other_actors_appearances = self._get_other_actors_appearances(
                actor_entity, current_stage
            )

            # 找到当前场景可去往的家园场景
            available_home_stages = self._get_available_home_stages(
                actor_entity, current_stage
            )

            # 生成请求处理器
            stage_narrative = current_stage.get(StageDescriptionComponent).narrative
            available_stage_names = [e.name for e in available_home_stages]
            chat_clients.append(
                DeepSeekClient(
                    name=actor_entity.name,
                    prompt=_build_action_planning_prompt(
                        current_stage=current_stage.name,
                        current_stage_narration=stage_narrative,
                        other_actors_appearances=other_actors_appearances,
                        available_home_stages=available_stage_names,
                        planning_turn_index=planning_turn_index,
                    ),
                    compressed_prompt=(
                        _build_compressed_planning_prompt(
                            current_stage=current_stage.name,
                            current_stage_narration=stage_narrative,
                            other_actors_appearances=other_actors_appearances,
                            available_home_stages=available_stage_names,
                            planning_turn_index=planning_turn_index,
                        )
                        if self._use_compressed_prompt
                        else None
                    ),
                    context=self._game.get_agent_context(actor_entity).context,
                )
            )

            # 测试用：向非玩家盟友注入一组连续的 mock 消息，模拟强制发起特定行动的场景。
            self._mock_inject_ally_equip_test(actor_entity)

        return chat_clients

    #######################################################################################################################################
    def _mock_inject_ally_equip_test(self, actor_entity: Entity) -> None:
        """【测试用】向非玩家盟友注入一组连续的 mock 消息，模拟强制发起特定行动的场景。

        只对非玩家 NPC（NPCComponent & ~PlayerComponent）生效。

        Args:
            actor_entity: 待注入的角色实体
        """
        if not actor_entity.has(NPCComponent) or actor_entity.has(PlayerComponent):
            return

        logger.debug(
            "这里清醒mock一个message 添加给学者的上下文，要求在后续的计划行动中不可以使用trans_stage 来移动场景！"
        )
        self._game.add_human_message(
            actor_entity,
            "这是一个测试消息，要求你在后续的计划行动中不可以使用trans_stage 来移动场景！",
        )

    #######################################################################################################################################
