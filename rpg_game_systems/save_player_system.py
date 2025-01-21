from entitas import ExecuteProcessor  # type: ignore
from typing import final, override
from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame


@final
class SavePlayerSystem(ExecuteProcessor):
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._save_players()

    ############################################################################################################
    def _save_players(self) -> None:
        for player_proxy in self._game.players:
            assert self._game._game_resource is not None
            path = self._game._game_resource.resolve_player_proxy_save_file_path(
                player_proxy.player_name
            )
            player_proxy.write_model_to_file(path)

    ############################################################################################################


############################################################################################################
