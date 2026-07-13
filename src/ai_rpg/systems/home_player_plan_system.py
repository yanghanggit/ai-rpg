"""家园玩家上下文注入系统。"""

from typing import Dict, Final, List, Optional, final
from loguru import logger
from ..models.messages import AIMessage, HumanMessage
from overrides import override
from ..entitas import Entity, Matcher, GroupEvent, ReactiveProcessor
from ..models import (
    AnnounceAction,
    StageDescriptionComponent,
    SpeakAction,
    WhisperAction,
    PlanAction,
    TransStageAction,
    ActorComponent,
    PlayerComponent,
    NPCComponent,
)
from ..game import DBGGame
from .home_planning_utils import (
    ActionPlanResponse,
    build_action_planning_prompt,
    build_compressed_planning_prompt,
    get_other_actors_appearances,
    get_available_home_stages,
)


#######################################################################################################################################
@final
class HomePlayerPlanSystem(ReactiveProcessor):
    """家园玩家上下文注入系统。"""

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
            and entity.has(PlayerComponent)
            and entity.has(ActorComponent)
            and entity.has(NPCComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        assert (
            len(entities) == 1
        ), "HomePlayerPlanSystem expects exactly one player entity at a time."
        self._inject_player_scene_context(entities[0])

    #######################################################################################################################################
    def _inject_player_scene_context(self, player_entity: Entity) -> None:
        """向玩家实体注入当前场景观察信息（不调用 LLM）。"""

        mock_response = self._build_player_action_response(player_entity)
        assert (
            mock_response is not None
        ), f"玩家 {player_entity.name} 无法构建影子 plan，跳过家园上下文注入。"

        current_stage = self._game.resolve_stage_entity(player_entity)
        assert (
            current_stage is not None
        ), f"玩家 {player_entity.name} 不在任何场景中，无法注入家园规划上下文。"

        # 获取当前场景中除玩家自身外的其他角色的外观信息
        other_actors_appearances = get_other_actors_appearances(
            self._game, player_entity, current_stage
        )

        # 获取玩家可用的家园场景列表
        available_home_stages = get_available_home_stages(
            self._game, player_entity, current_stage
        )

        # 获取当前场景的叙事描述
        stage_narrative = current_stage.get(StageDescriptionComponent).narrative

        # 提取可用家园场景的名称列表
        available_stage_names = [e.name for e in available_home_stages]

        # 构建完整的行动规划提示，包括当前场景、场景叙事、其他角色外观信息以及可用家园场景列表
        full_prompt = build_action_planning_prompt(
            current_stage=current_stage.name,
            current_stage_narration=stage_narrative,
            other_actors_appearances=other_actors_appearances,
            available_home_stages=available_stage_names,
        )

        # 如果配置了使用压缩提示，则构建压缩后的行动规划提示并发送给游戏系统
        if self._use_compressed_prompt:
            compressed_prompt = build_compressed_planning_prompt(
                current_stage=current_stage.name,
                current_stage_narration=stage_narrative,
                other_actors_appearances=other_actors_appearances,
                available_home_stages=available_stage_names,
            )

            # 将压缩后的行动规划提示发送给游戏系统，附带玩家的全量提示以便参考
            self._game.add_human_message(
                player_entity,
                HumanMessage(
                    content=compressed_prompt,
                    home_actor_planning=player_entity.name,
                    home_actor_full_prompt=full_prompt,
                ),
            )
        else:

            # 如果未配置使用压缩提示，则直接将完整的行动规划提示发送给游戏系统
            self._game.add_human_message(
                player_entity,
                HumanMessage(
                    content=full_prompt,
                    home_actor_planning=player_entity.name,
                ),
            )

        # 将 AI 的响应消息添加上下文。
        self._game.add_ai_message(
            player_entity, AIMessage(content=mock_response.model_dump_json(indent=2))
        )

    #######################################################################################################################################
    def _build_player_action_response(
        self, player_entity: Entity
    ) -> Optional[ActionPlanResponse]:
        """根据玩家当前挂载的主动行动组件构建等效的 ActionPlanResponse（影子 plan）。"""

        response = ActionPlanResponse()

        if player_entity.has(SpeakAction):
            response.speak = player_entity.get(SpeakAction).target_messages

        if player_entity.has(WhisperAction):
            response.whisper = player_entity.get(WhisperAction).target_messages

        if player_entity.has(AnnounceAction):
            response.announce = player_entity.get(AnnounceAction).message

        if player_entity.has(TransStageAction):
            response.trans_stage = player_entity.get(TransStageAction).target_stage_name

        if not any(
            [
                response.speak,
                response.whisper,
                response.announce,
                response.trans_stage,
            ]
        ):
            logger.warning(
                f"HomePlayerPlanSystem: 玩家 {player_entity.name} 被挂载 PlanAction 但没有任何主动行动组件，跳过影子 plan 构建"
            )
            return None

        return response

    #######################################################################################################################################
