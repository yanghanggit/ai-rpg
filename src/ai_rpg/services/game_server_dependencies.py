from typing import Annotated, Optional
from fastapi import Depends
from ..game.game_server import GameServer


_game_server_instance: Optional[GameServer] = None


###############################################################################################################################################
def get_game_server() -> GameServer:
    global _game_server_instance
    if _game_server_instance is None:
        _game_server_instance = GameServer()
    return _game_server_instance


###############################################################################################################################################
CurrentGameServer = Annotated[GameServer, Depends(get_game_server)]
