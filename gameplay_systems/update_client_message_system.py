from entitas import ExecuteProcessor, Entity, Matcher  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from player.player_proxy import PlayerProxy
from rpg_game.rpg_entitas_context import RPGEntitasContext
from my_components.action_components import (
    StageNarrateAction,
    GoToAction,
)
from typing import final, override
from loguru import logger
from rpg_game.rpg_game import RPGGame
from my_models.event_models import AgentEvent


@final
class UpdateClientMessageSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        for player_proxy in self._game.players:
            player_entity = self._context.get_player_entity(player_proxy.name)
            if player_entity is None or player_proxy is None:
                continue

            self._add_message_to_player_proxy(player_proxy, player_entity)

    ############################################################################################################
    def _add_message_to_player_proxy(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:

        # 环境描写
        self._stage_enviro_narrate_action_2_message(player_proxy, player_entity)

        # 如果有登陆信息就直接上登陆信息
        player_proxy.flush_kickoff_messages()

        # 去往信息？
        self._go_to_action_2_message(player_proxy, player_entity)

    ############################################################################################################
    def _stage_enviro_narrate_action_2_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        stage = self._context.safe_get_stage_entity(player_entity)
        if stage is None:
            return
        if not stage.has(StageNarrateAction):
            return

        stage_narrate_action = stage.get(StageNarrateAction)
        if len(stage_narrate_action.values) == 0:
            return

        message = " ".join(stage_narrate_action.values)
        player_proxy.add_stage_message(
            stage_narrate_action.name, AgentEvent(message=message)
        )

    ############################################################################################################
    def _go_to_action_2_message(
        self, player_proxy: PlayerProxy, player_entity: Entity
    ) -> None:
        player_entity_stage = self._context.safe_get_stage_entity(player_entity)
        entities = self._context.get_group(Matcher(GoToAction)).entities
        for entity in entities:

            if entity == player_entity:
                continue

            his_stage_entity = self._context.safe_get_stage_entity(entity)
            if his_stage_entity != player_entity_stage:
                continue

            go_to_action = entity.get(GoToAction)
            if len(go_to_action.values) == 0:
                logger.error("go_to_action_2_message error")
                continue

            stage_name = go_to_action.values[0]
            player_proxy.add_actor_message(
                go_to_action.name,
                AgentEvent(message=f"""准备去往{stage_name}"""),
            )


############################################################################################################
