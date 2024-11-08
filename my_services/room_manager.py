from typing import Optional
from rpg_game.web_game import WebGame
from player.player_proxy import PlayerProxy
from my_models.config_models import GenGamesConfigModel
from my_services.game_state_manager import GameStateManager, GameState


class Room:

    def __init__(self, user_name: str) -> None:
        self._user_name = user_name
        self._game: Optional[WebGame] = None

    def get_player(self) -> Optional[PlayerProxy]:
        if self._game is None:
            return None
        return self._game.get_player(self._user_name)

    def get_player_actor_name(self) -> str:
        player = self.get_player()
        if player is None:
            return ""
        return player.actor_name


class RoomManager:

    def __init__(self) -> None:
        self._room: Optional[Room] = None
        self._state: GameStateManager = GameStateManager(GameState.UNLOGGED)
        self._game_config: GenGamesConfigModel = GenGamesConfigModel()


RoomManagerInstance = RoomManager()
