from typing import Annotated, Final, Optional

from fastapi import Depends

from ..game_services.room_manager import RoomManager


###############################################################################################################################################
class GameServer:
    def __init__(
        self,
        room_manager: RoomManager,
    ) -> None:
        self._room_manager: Final[RoomManager] = room_manager

    ###############################################################################################################################################
    @property
    def room_manager(self) -> RoomManager:
        return self._room_manager

    ###############################################################################################################################################


_game_server: Optional[GameServer] = None


###############################################################################################################################################
def get_game_server_instance() -> GameServer:
    global _game_server
    if _game_server is None:
        _game_server = GameServer(
            room_manager=RoomManager(),
        )
    return _game_server


###############################################################################################################################################
GameServerInstance = Annotated[GameServer, Depends(get_game_server_instance)]
