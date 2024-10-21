from entitas import ExecuteProcessor, Entity, Matcher  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from player.player_proxy import PlayerProxy
from rpg_game.rpg_entitas_context import RPGEntitasContext
from gameplay_systems.action_components import (
    StageNarrateAction,
    GoToAction,
)
from typing import override
from loguru import logger
from rpg_game.rpg_game import RPGGame
from my_data.model_def import AgentEvent


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

        player_proxy.add_system_message(
            AgentEvent(message_content=f"游戏运行次数:{self._game._runtime_game_round}")
        )

        self._stage_enviro_narrate_action_2_message(player_proxy, player_entity)
        # self._show_login_messages_then_clear(
        #     player_proxy, player_entity
        # )  # 先把缓存的消息推送出去，在场景描述之后
        player_proxy.flush_login_messages()

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
            stage_narrate_action.name, AgentEvent(message_content=message)
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
                AgentEvent(message_content=f"""准备去往{stage_name}"""),
            )

    ############################################################################################################
    # def _show_login_messages_then_clear(
    #     self, player_proxy: PlayerProxy, player_entity: Entity
    # ) -> None:
    #     # todo
    #     for message in player_proxy.model.login_messages:
    #         player_proxy.add_actor_message(message.sender, message.event)
    #     player_proxy.model.login_messages.clear()


############################################################################################################
