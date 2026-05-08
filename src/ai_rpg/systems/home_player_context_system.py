"""家园玩家上下文注入系统。

响应 PlanAction 触发，仅处理玩家实体：
将玩家当前动作（或被动观察）序列化为标准 ActionPlanResponse，
写入对话历史，与 NPC 路径保持一致的 context 格式。
"""

from typing import Dict, Final, final
from ..models.messages import AIMessage
from overrides import override
from ..entitas import Entity, Matcher, GroupEvent, ReactiveProcessor
from ..models import (
    AnnounceAction,
    StageDescriptionComponent,
    SpeakAction,
    WhisperAction,
    PlanAction,
    TransStageAction,
    EquipItemAction,
    HomeComponent,
    MindEvent,
    ActorComponent,
    PlayerComponent,
)
from ..game import TCGGame
from .home_planning_utils import (
    ActionPlanResponse,
    _PLAYER_ACTIVE_ACTION_TYPES,
    _build_action_planning_prompt,
    _build_compressed_planning_prompt,
    _format_mind_notification,
)


#######################################################################################################################################
@final
class HomePlayerContextSystem(ReactiveProcessor):
    """家园玩家上下文注入系统。

    响应式处理器，监听 PlanAction 组件触发，仅对持有 PlayerComponent 的实体生效。
    不调用 LLM，而是将玩家当前动作组件序列化为 ActionPlanResponse 写入对话历史，
    并自增全局家园规划回合计数器（应注册在 HomeActorPlanSystem 之前）。

    Attributes:
        _game: 游戏实例引用
        _use_compressed_prompt: 是否使用压缩 prompt 机制，与 HomeActorPlanSystem 保持一致。
    """

    def __init__(self, game: TCGGame, use_compressed_prompt: bool = True) -> None:
        super().__init__(game)
        self._game: Final[TCGGame] = game
        self._use_compressed_prompt: Final[bool] = use_compressed_prompt

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(PlanAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return (
            entity.has(PlanAction)
            and entity.has(PlayerComponent)
            and entity.has(ActorComponent)
        )

    #######################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        # 自增全局家园规划回合计数器（本系统注册在 HomeActorPlanSystem 之前，负责 turn 推进）
        self._game._world.home_planning_turn_index += 1
        planning_turn = self._game._world.home_planning_turn_index

        for player_entity in entities:
            self._inject_player_scene_context(player_entity, planning_turn)

    #######################################################################################################################################
    def _inject_player_scene_context(
        self, player_entity: Entity, planning_turn_index: int
    ) -> None:
        """向玩家实体注入当前场景观察信息（不调用 LLM）。

        Args:
            player_entity: 玩家实体
            planning_turn_index: 全局家园规划回合编号
        """
        current_stage = self._game.resolve_stage_entity(player_entity)
        assert current_stage is not None

        other_actors_appearances = self._get_other_actors_appearances(
            player_entity, current_stage
        )
        available_home_stages = self._get_available_home_stages(
            player_entity, current_stage
        )

        stage_narrative = current_stage.get(StageDescriptionComponent).narrative
        available_stage_names = [e.name for e in available_home_stages]

        full_prompt = _build_action_planning_prompt(
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
                player_entity,
                compressed_prompt,
                home_actor_planning=player_entity.name,
                home_actor_full_prompt=full_prompt,
            )
        else:
            self._game.add_human_message(
                player_entity,
                full_prompt,
                home_actor_planning=player_entity.name,
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
                    message=_format_mind_notification(
                        player_entity.name, mock_response.mind
                    ),
                    actor=player_entity.name,
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

        if player_entity.has(EquipItemAction):
            equip_action = player_entity.get(EquipItemAction)
            response.equip_weapon = equip_action.weapon
            response.equip_armor = equip_action.armor
            response.equip_accessory = equip_action.accessory

        if not any(
            [
                response.speak,
                response.whisper,
                response.announce,
                response.trans_stage,
            ]
        ) and not any(
            x is not None
            for x in [
                response.equip_weapon,
                response.equip_armor,
                response.equip_accessory,
            ]
        ):
            response.mind = passive_mind

        return response

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
        """获取玩家可前往的家园场景集合（排除当前场景）。

        Args:
            actor_entity: 玩家实体
            current_stage: 当前所在场景实体

        Returns:
            可前往的家园场景实体集合
        """
        home_stage_entities = self._game.get_group(
            Matcher(all_of=[HomeComponent])
        ).entities.copy()
        home_stage_entities.discard(current_stage)
        return home_stage_entities

    #######################################################################################################################################
