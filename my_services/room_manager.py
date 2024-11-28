from typing import Optional, Dict
from my_models.config_models import GlobalConfigModel
from my_services.room import Room


class RoomManager:

    def __init__(self) -> None:

        self._rooms: Dict[str, Room] = {}
        self._global_config: GlobalConfigModel = GlobalConfigModel()

    ###############################################################################################################################################
    @property
    def global_config(self) -> GlobalConfigModel:
        return self._global_config

    ###############################################################################################################################################
    @global_config.setter
    def global_config(self, value: GlobalConfigModel) -> None:
        assert len(value.game_configs) > 0, "no game config"
        self._global_config = value

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
