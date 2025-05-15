from game_services.game_server import GameServer
from fastapi import Depends
from typing import Annotated
from game_services.room_manager import RoomManager


###############################################################################################################################################
def initialize_game_server_instance() -> GameServer:

    assert GameServer._singleton is None

    if GameServer._singleton is None:
        GameServer._singleton = GameServer(
            room_manager=RoomManager(),
        )

    return GameServer._singleton


###############################################################################################################################################
def get_game_server_instance() -> GameServer:
    assert GameServer._singleton is not None
    return GameServer._singleton


###############################################################################################################################################
GameServerInstance = Annotated[GameServer, Depends(get_game_server_instance)]
###############################################################################################################################################
