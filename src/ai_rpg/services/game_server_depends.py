from typing import Annotated, Optional
from fastapi import Depends
from ..game.game_server import GameServer


_game_server: Optional[GameServer] = None


###############################################################################################################################################
def get_game_server_instance() -> GameServer:
    global _game_server
    if _game_server is None:
        _game_server = GameServer()
    return _game_server


###############################################################################################################################################
GameServerInstance = Annotated[GameServer, Depends(get_game_server_instance)]
