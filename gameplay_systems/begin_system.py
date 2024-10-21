from entitas import ExecuteProcessor  # type: ignore
from typing import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame
from my_data.model_def import AgentEvent


class BeginSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        # 每次进入这个系统就增加一个回合
        self._game._runtime_game_round += 1
        logger.debug(f"self._context._execute_count = {self._game._runtime_game_round}")

        # 清除这个临时用的数据结构
        self._context._round_messages = {}

        # 加一个回合的消息
        self._add_game_round_client_message()

    ############################################################################################################
    def _add_game_round_client_message(self) -> None:

        for player_proxy in self._game.players:

            player_entity = self._context.get_player_entity(player_proxy.name)
            if player_entity is None or player_proxy is None:
                continue

            player_proxy.add_system_message(
                AgentEvent(
                    message_content=f"Game Round = {self._game._runtime_game_round}"
                )
            )


############################################################################################################
