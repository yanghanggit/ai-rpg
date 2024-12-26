from services.game_server import GameServer
from fastapi import FastAPI, Depends
from typing import Annotated
from services.room_manager import RoomManager
from services.game_server import ServerConfig


###############################################################################################################################################
def initialize_game_server_instance(
    server_ip_address: str = "127.0.0.1", server_port: int = 8000
) -> GameServer:

    assert GameServer._singleton is None
    assert server_ip_address is not None and server_port is not None
    if GameServer._singleton is None:
        GameServer._singleton = GameServer(
            fast_api=FastAPI(),
            room_manager=RoomManager(),
            server_config=ServerConfig(server_ip_address, server_port),
        )

    return GameServer._singleton


###############################################################################################################################################
def get_game_server_instance() -> GameServer:
    assert GameServer._singleton is not None
    return GameServer._singleton


###############################################################################################################################################
GameServerInstance = Annotated[GameServer, Depends(get_game_server_instance)]
###############################################################################################################################################
