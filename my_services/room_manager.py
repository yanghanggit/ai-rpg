from typing import Optional, Dict
from rpg_game.web_game import WebGame
from player.player_proxy import PlayerProxy
from my_models.config_models import GenGamesConfigModel
from my_services.game_state_manager import GameStateController, GameState
from pathlib import Path
from loguru import logger


class Room:

    def __init__(self, user_name: str) -> None:
        self._user_name = user_name
        self._game: Optional[WebGame] = None
        self._state_controller: GameStateController = GameStateController(
            GameState.UNLOGGED
        )

    ###############################################################################################################################################
    @property
    def game(self) -> Optional[WebGame]:
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


class RoomManager:

    def __init__(self) -> None:

        self._rooms: Dict[str, Room] = {}
        self._game_config: GenGamesConfigModel = GenGamesConfigModel()

    ###############################################################################################################################################
    @property
    def game_config(self) -> GenGamesConfigModel:
        return self._game_config

    ###############################################################################################################################################
    def has_room(self, user_name: str) -> bool:
        return user_name in self._rooms

    ###############################################################################################################################################
    def get_room(self, user_name: str) -> Optional[Room]:
        return self._rooms.get(user_name, None)

    ###############################################################################################################################################
    def create_room(self, user_name: str) -> Room:
        if self.has_room(user_name):
            assert False, f"room {user_name} already exists"
        room = Room(user_name)
        self._rooms[user_name] = room
        return room

    ###############################################################################################################################################
    def remove_room(self, room: Room) -> None:
        user_name = room._user_name
        assert user_name in self._rooms
        self._rooms.pop(user_name, None)

    ###############################################################################################################################################
    def read_game_config(self, game_config_file_path: Path) -> None:
        assert game_config_file_path.exists()
        try:
            self._game_config = GenGamesConfigModel.model_validate_json(
                game_config_file_path.read_text(encoding="utf-8")
            )

        except Exception as e:
            logger.error(e)
            assert False, e

    ###############################################################################################################################################


RoomManagerInstance = RoomManager()
