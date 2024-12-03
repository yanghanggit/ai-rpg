from entitas import ExecuteProcessor, Entity, Matcher  # type: ignore
from game.rpg_game_context import RPGGameContext
from player.player_proxy import PlayerProxy
from game.rpg_game_context import RPGGameContext
from components.action_components import (
    # StageNarrateAction,
    StageTagAction,
    GoToAction,
)
from typing import final, override
from loguru import logger
from game.rpg_game import RPGGame
from models.event_models import AgentEvent, StageTagEvent
from components.components import StageComponent
import gameplay_systems.stage_entity_utils


@final
class UpdateClientMessageSystem(ExecuteProcessor):
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        for player_proxy in self._game.players:
            player_entity = self._context.get_player_entity(player_proxy.player_name)
            if player_entity is None or player_proxy is None:
                continue

            self._add_message_to_player_proxy(player_proxy, player_entity)

    ############################################################################################################
    def _add_message_to_player_proxy(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:

        # 场景描述
        self._add_stage_narrate_action_message(player_proxy, player_entity)

        # 场景标记
        self._add_stage_tag_action_message(player_proxy, player_entity)

        # 如果有登陆信息就直接上登陆信息
        player_proxy.clear_and_send_kickoff_messages()

        # 去往信息？
        self._add_go_to_action_message(player_proxy, player_entity)

    ############################################################################################################
    def _add_stage_narrate_action_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        stage_entity = self._context.safe_get_stage_entity(player_entity)
        if stage_entity is None:
            return

        player_proxy.add_stage_message(
            stage_entity.get(StageComponent).name,
            AgentEvent(
                message=gameplay_systems.stage_entity_utils.extract_current_stage_narrative(
                    self._context, stage_entity
                )
            ),
        )

    ############################################################################################################
    def _add_stage_tag_action_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        stage = self._context.safe_get_stage_entity(player_entity)
        if stage is None:
            return
        if not stage.has(StageTagAction):
            return

        stage_tag_action = stage.get(StageTagAction)
        if len(stage_tag_action.values) == 0:
            return

        message = ",".join(stage_tag_action.values)
        player_proxy.add_stage_message(
            stage_tag_action.name,
            StageTagEvent(message=message, stage_tags=stage_tag_action.values),
        )

    ############################################################################################################
    def _add_go_to_action_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:

        current_player_stage = self._context.safe_get_stage_entity(player_entity)
        assert current_player_stage is not None, "current_player_stage error"
        stage_name = self._context.safe_get_entity_name(current_player_stage)

        stage_tag_component = (
            self._context.query_component_system.get_stage_tag_component_class(
                stage_name
            )
        )
        if stage_tag_component is None:
            logger.error("stage_tag_component error")
            return

        entities = self._context.get_group(
            Matcher(all_of=[GoToAction, stage_tag_component])
        ).entities
        for target_entity in entities:

            if target_entity == player_entity:
                continue

            go_to_action = target_entity.get(GoToAction)
            if len(go_to_action.values) == 0:
                logger.error("go_to_action_2_message error")
                continue

            stage_name = go_to_action.values[0]
            player_proxy.add_actor_message(
                go_to_action.name,
                AgentEvent(message=f"""准备去往{stage_name}"""),
            )


############################################################################################################
