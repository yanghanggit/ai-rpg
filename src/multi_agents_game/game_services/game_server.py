from typing import Final, Optional
from ..game_services.room_manager import RoomManager
from fastapi import Depends
from typing import Annotated
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


game_server: Optional[GameServer] = None


###############################################################################################################################################
def get_game_server_instance() -> GameServer:
    global game_server
    if game_server is None:
        game_server = GameServer(
            room_manager=RoomManager(),
        )
    return game_server


###############################################################################################################################################
GameServerInstance = Annotated[GameServer, Depends(get_game_server_instance)]
