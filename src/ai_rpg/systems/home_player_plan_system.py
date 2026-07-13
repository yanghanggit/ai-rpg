"""家园玩家上下文注入系统。"""

from typing import Dict, Final, final, Dict, List
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
    MindEvent,
    ActorComponent,
    PlayerComponent,
    NPCComponent,
)
from ..game import DBGGame
from .home_planning_utils import (
    ActionPlanResponse,
    _PLAYER_ACTIVE_ACTION_TYPES,
    build_action_planning_prompt,
    build_compressed_planning_prompt,
    format_mind_notification,
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
        for player_entity in entities:
            self._inject_player_scene_context(player_entity)

    #######################################################################################################################################
    def _inject_player_scene_context(self, player_entity: Entity) -> None:
        """向玩家实体注入当前场景观察信息（不调用 LLM）。

        Args:
            player_entity: 玩家实体
        """
        current_stage = self._game.resolve_stage_entity(player_entity)
        assert (
            current_stage is not None
        ), f"玩家 {player_entity.name} 不在任何场景中，无法注入家园规划上下文。"

        other_actors_appearances = get_other_actors_appearances(
            self._game, player_entity, current_stage
        )
        available_home_stages = get_available_home_stages(
            self._game, player_entity, current_stage
        )

        stage_narrative = current_stage.get(StageDescriptionComponent).narrative
        available_stage_names = [e.name for e in available_home_stages]

        full_prompt = build_action_planning_prompt(
            current_stage=current_stage.name,
            current_stage_narration=stage_narrative,
            other_actors_appearances=other_actors_appearances,
            available_home_stages=available_stage_names,
        )
        if self._use_compressed_prompt:
            compressed_prompt = build_compressed_planning_prompt(
                current_stage=current_stage.name,
                current_stage_narration=stage_narrative,
                other_actors_appearances=other_actors_appearances,
                available_home_stages=available_stage_names,
            )
            self._game.add_human_message(
                player_entity,
                HumanMessage(
                    content=compressed_prompt,
                    home_actor_planning=player_entity.name,
                    home_actor_full_prompt=full_prompt,
                ),
            )
        else:
            self._game.add_human_message(
                player_entity,
                HumanMessage(
                    content=full_prompt,
                    home_actor_planning=player_entity.name,
                ),
            )

        # 判断玩家本轮是否有主动动作
        has_action = any(
            player_entity.has(action_type)
            for action_type in _PLAYER_ACTIVE_ACTION_TYPES
        )
        passive_mind = "" if has_action else f"身处{current_stage.name}，待命。"

        mock_response = self._build_player_action_response(player_entity, passive_mind)
        self._game.add_ai_message(
            player_entity, AIMessage(content=mock_response.model_dump_json(indent=2))
        )

        # 被动观察轮：模拟 mind 通知，与 NPC 路径对齐
        if mock_response.mind != "":
            self._game.notify_entities(
                {player_entity},
                MindEvent(
                    message=format_mind_notification(
                        player_entity.name, mock_response.mind
                    ),
                    actor=player_entity.name,
                    stage=current_stage.name,
                    content=mock_response.mind,
                ),
            )

    #######################################################################################################################################
    def _build_player_action_response(
        self, player_entity: Entity, passive_mind: str = ""
    ) -> ActionPlanResponse:
        """根据玩家当前动作组件构建等效的 ActionPlanResponse。

        有主动动作时 mind 为空；无任何动作（被动观察轮）时用 passive_mind 填入。

        Args:
            player_entity: 玩家实体
            passive_mind: 被动观察轮时使用的 mind 文本

        Returns:
            模拟的 ActionPlanResponse
        """
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
            response.mind = passive_mind

        return response

    #######################################################################################################################################
    # def _get_other_actors_appearances(
    #     self, actor_entity: Entity, current_stage: Entity
    # ) -> Dict[str, str]:
    #     """获取当前场景内除自身以外的所有角色外观描述。

    #     Args:
    #         actor_entity: 当前角色实体（将被排除）
    #         current_stage: 当前所在场景实体

    #     Returns:
    #         其他角色的外观描述（角色名 -> 外观）
    #     """
    #     appearances = self._game.get_actor_appearances_in_stage(current_stage)
    #     appearances.pop(actor_entity.name, None)
    #     return appearances

    # #######################################################################################################################################
    # def _get_available_home_stages(
    #     self, actor_entity: Entity, current_stage: Entity
    # ) -> set[Entity]:
    #     """获取玩家可前往的家园场景集合（排除当前场景）。

    #     Args:
    #         actor_entity: 玩家实体
    #         current_stage: 当前所在场景实体

    #     Returns:
    #         可前往的家园场景实体集合
    #     """
    #     home_stage_entities = self._game.get_group(
    #         Matcher(all_of=[HomeComponent])
    #     ).entities.copy()
    #     home_stage_entities.discard(current_stage)
    #     return home_stage_entities

    #######################################################################################################################################
