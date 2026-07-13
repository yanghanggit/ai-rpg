from typing import Dict, Final, List, final
from ..models.messages import HumanMessage
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
    MindEvent,
    ActorComponent,
    NPCComponent,
    PlayerComponent,
)
from ..utils import extract_json_from_code_block
from ..game import DBGGame
from .home_planning_utils import (
    ActionPlanResponse,
    build_action_planning_prompt,
    build_compressed_planning_prompt,
    format_mind_notification,
    get_other_actors_appearances,
    get_available_home_stages,
)


#######################################################################################################################################
@final
class HomeNpcPlanSystem(ReactiveProcessor):
    """家园 NPC 自主行动规划系统。"""

    def __init__(self, game: DBGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
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
            and entity.has(NPCComponent)
            and not entity.has(PlayerComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:

        # 能进入本系统的 NPC 均已由客户端显式指定需要本轮真正规划，无需再根据玩家状态判断是否进入待命。

        # 构建每个 NPC 的聊天客户端
        chat_clients: List[DeepSeekClient] = []
        for actor_entity in entities:
            chat_clients.append(self._build_client(actor_entity))

            # 这句是为了防止NPC乱跑用的，暂时先放这里。
            self._mock_inject_context(actor_entity)

        # 批量请求 LLM 合成行动规划
        await DeepSeekClient.batch_chat(clients=chat_clients)

        # 解析 LLM 响应并转化为游戏行动组件，保存对话历史
        for chat_client in chat_clients:
            self._execute_actor_actions(chat_client)

    #######################################################################################################################################
    def _execute_actor_actions(self, chat_client: DeepSeekClient) -> None:
        """执行角色的行动决策。"""

        actor_entity = self._game.get_entity_by_name(chat_client.name)
        assert (
            actor_entity is not None
        ), f"Cannot find entity by name: {chat_client.name}"

        # 检查 LLM 是否返回了有效的 AI 消息，如果没有则记录错误并返回
        if chat_client.response_ai_message is None:
            logger.error(f"HomeNpcPlanSystem: [{actor_entity.name}] LLM 返回空响应")
            return

        try:
            # 验证响应
            validated_response = ActionPlanResponse.model_validate_json(
                extract_json_from_code_block(chat_client.response_content)
            )
        except Exception as e:
            logger.error(f"Exception: {e}")
            return

        # 添加上下文！存入压缩版 prompt，附挂原始全量 prompt 供检索
        if self._use_compressed_prompt:
            self._game.add_human_message(
                actor_entity,
                HumanMessage(
                    content=chat_client.compressed_prompt,
                    home_actor_planning=actor_entity.name,
                    home_actor_full_prompt=chat_client.prompt,
                ),
            )
        else:
            self._game.add_human_message(
                actor_entity,
                HumanMessage(
                    content=chat_client.prompt,
                    home_actor_planning=actor_entity.name,
                ),
            )

        # 添加 AI 响应消息到上下文。
        self._game.add_ai_message(actor_entity, chat_client.response_ai_message)

        # 将验证后的行动规划响应转化为游戏行动组件，并处理内心独白通知
        self._apply_actor_action_response(actor_entity, validated_response)

    #######################################################################################################################################
    def _apply_actor_action_response(
        self, actor_entity: Entity, validated_response: ActionPlanResponse
    ) -> None:
        """将验证后的行动规划响应转化为游戏行动组件，并处理内心独白通知。"""

        # 添加内心独白: 上下文！，这里做直接添加与通知处理
        if validated_response.mind != "":

            stage_entity = self._game.resolve_stage_entity(actor_entity)
            assert stage_entity is not None, "actor无所在场景是有问题的"
            self._game.notify_entities(
                set({actor_entity}),
                MindEvent(
                    message=format_mind_notification(
                        actor_entity.name, validated_response.mind
                    ),
                    actor=actor_entity.name,
                    stage=stage_entity.name,
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

    #######################################################################################################################################
    def _build_client(self, entity: Entity) -> DeepSeekClient:
        """为角色创建聊天客户端。"""
        # 找到当前场景
        current_stage = self._game.resolve_stage_entity(entity)
        assert current_stage is not None, "当前角色所在的场景不存在"

        # 找到当前场景内所有角色 & 他们的外观描述（不含自己）
        other_actors_appearances = get_other_actors_appearances(
            self._game, entity, current_stage
        )

        # 找到当前场景可去往的家园场景
        available_home_stages = get_available_home_stages(
            self._game, entity, current_stage
        )

        # 生成请求处理器
        stage_narrative = current_stage.get(StageDescriptionComponent).narrative
        available_stage_names = [e.name for e in available_home_stages]

        # 生成行动规划提示词

        return DeepSeekClient(
            name=entity.name,
            prompt=build_action_planning_prompt(
                current_stage=current_stage.name,
                current_stage_narration=stage_narrative,
                other_actors_appearances=other_actors_appearances,
                available_home_stages=available_stage_names,
            ),
            compressed_prompt=(
                build_compressed_planning_prompt(
                    current_stage=current_stage.name,
                    current_stage_narration=stage_narrative,
                    other_actors_appearances=other_actors_appearances,
                    available_home_stages=available_stage_names,
                )
                if self._use_compressed_prompt
                else None
            ),
            context=self._game.get_agent_context(entity).context,
        )

    #######################################################################################################################################
    def _mock_inject_context(self, actor_entity: Entity) -> None:
        """【测试用】向非玩家盟友注入一组连续的 mock 消息，模拟强制发起特定行动的场景。"""
        self._game.add_human_message(
            actor_entity,
            HumanMessage(
                content="这是一个测试消息，要求你在后续的计划行动中不可以使用trans_stage 来移动场景！"
            ),
        )

    #######################################################################################################################################
