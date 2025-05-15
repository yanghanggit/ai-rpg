from typing import Optional, Final
from game_services.room_manager import RoomManager
from fastapi import FastAPI


###############################################################################################################################################
class GameServer:

    _singleton: Optional["GameServer"] = None

    def __init__(
        self,
        room_manager: RoomManager,
    ) -> None:
        self._fast_api: Optional[FastAPI] = None
        self._room_manager: Final[RoomManager] = room_manager

    ###############################################################################################################################################
    @property
    def room_manager(self) -> RoomManager:
        return self._room_manager

    ###############################################################################################################################################
