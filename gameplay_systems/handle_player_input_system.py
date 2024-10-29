from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from my_components.components import PlanningAllowedComponent
from loguru import logger


############################################################################################################
@final
class HandlePlayerInputSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        # 1. 遍历所有的玩家,
        for player_proxy in self._game.players:

            player_entity = self._context.get_player_entity(player_proxy.name)
            if player_entity is None:
                assert (
                    False
                ), f"player_entity is None, player_proxy.name={player_proxy.name}"
                continue

            if not player_entity.has(PlanningAllowedComponent):
                logger.info(
                    f"player_entity has no PlanningAllowedComponent, player_proxy.name={player_proxy.name}"
                )
                continue

            for command in player_proxy._commands:
                command.execute(self._game, player_proxy)

        # 2. 清空所有玩家的命令
        for player_proxy in self._game.players:
            player_proxy._commands.clear()


############################################################################################################
