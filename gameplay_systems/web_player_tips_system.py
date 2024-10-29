from entitas import Entity, ExecuteProcessor  # type: ignore
from typing import final, override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from gameplay_systems.components import (
    PlayerComponent,
    ActorComponent,
)
from player.player_proxy import PlayerProxy
from my_models.models_def import AgentEvent
from rpg_game.web_game import WebGame
from loguru import logger


@final
class WebPlayerTipsSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._test_index: int = 0

    ############################################################################################################
    @override
    def execute(self) -> None:
        if not isinstance(self._game, WebGame):
            logger.warning("不是终端游戏，无法使用这个系统")
            return

        self._test_index += 1
        self._add_tips()

    ############################################################################################################
    def _add_tips(self) -> None:

        for player_proxy in self._game.players:

            if player_proxy is None:
                continue

            player_entity = self._context.get_player_entity(player_proxy.name)
            if player_entity is None:
                continue

            assert player_entity is not None
            assert player_entity.has(PlayerComponent)
            assert player_entity.has(ActorComponent)

            # 当前场景能去往的场景
            self._add_test_tips(player_proxy, player_entity)

    ############################################################################################################
    def _add_test_tips(self, player_proxy: PlayerProxy, player_entity: Entity) -> None:
        assert player_entity is not None
        assert player_proxy is not None

        actor_name = self._context.safe_get_entity_name(player_entity)
        player_proxy.add_tip_message(
            actor_name,
            AgentEvent(message_content=f"这是一个测试的消息{self._test_index}"),
        )

    ############################################################################################################
