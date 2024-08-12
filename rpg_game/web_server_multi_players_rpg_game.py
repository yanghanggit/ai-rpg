from rpg_game.rpg_game import RPGGame
from rpg_game.rpg_entitas_context import RPGEntitasContext


class WebServerMultiplayersRPGGame(RPGGame):
    
    def __init__(self, name: str, context: RPGEntitasContext):
        super().__init__(name, context)
        self._host: str = ""

    def set_host(self, host: str) -> None:
        assert self._host == "", "Host already set"
        self._host = host
