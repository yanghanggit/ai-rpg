from typing import Optional
from game.web_rpg_game import WebRPGGame
from player.player_proxy import PlayerProxy
from services.game_state_manager import GameStateController, GameState


class Room:

    def __init__(self, user_name: str) -> None:
        self._user_name = user_name
        self._game: Optional[WebRPGGame] = None
        self._state_controller: GameStateController = GameStateController(
            GameState.UNLOGGED
        )

    ###############################################################################################################################################
    @property
    def game(self) -> Optional[WebRPGGame]:
        return self._game

    ###############################################################################################################################################
    def get_player(self) -> Optional[PlayerProxy]:
        if self._game is None:
            return None
        return self._game.get_player(self._user_name)

    ###############################################################################################################################################
    def get_player_actor_name(self) -> str:
        player = self.get_player()
        if player is None:
            return ""
        return player.actor_name

    ###############################################################################################################################################
    @property
    def state(self) -> GameState:
        return self._state_controller.state

    ###############################################################################################################################################
    @property
    def state_controller(self) -> GameStateController:
        return self._state_controller

    ###############################################################################################################################################
