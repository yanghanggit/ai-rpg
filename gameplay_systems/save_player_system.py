from entitas import ExecuteProcessor  # type: ignore
from typing import override
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from pathlib import Path
from player.player_proxy import PlayerProxyModel
from loguru import logger


class SavePlayerSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
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
                player_proxy.name
            )
            self._write_model(player_proxy.model, path)

    ############################################################################################################
    def _write_model(
        self, player_proxy_model: PlayerProxyModel, write_path: Path
    ) -> int:

        try:
            dump_json = player_proxy_model.model_dump_json()
            return write_path.write_text(dump_json, encoding="utf-8")

        except Exception as e:
            logger.error(f"写文件失败: {write_path}, e = {e}")

        return -1


############################################################################################################
