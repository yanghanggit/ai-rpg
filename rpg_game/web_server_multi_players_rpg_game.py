from rpg_game.rpg_game import RPGGame
from my_entitas.extended_context import ExtendedContext


class WebServerMultiplayersRPGGame(RPGGame):
    
    def __init__(self, name: str, context: ExtendedContext):
        super().__init__(name, context)
        self._host: str = ""

    def set_host(self, host: str) -> None:
        assert self._host == "", "Host already set"
        self._host = host
