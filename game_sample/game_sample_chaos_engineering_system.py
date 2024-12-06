import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from typing import Any, Optional, final, override
from game.rpg_game import RPGGame


@final
class GameSampleChaosEngineeringSystem(IChaosEngineering):

    def __init__(self) -> None:
        super().__init__()
        self._rpg_game: Optional[RPGGame] = None

    @property
    def rpg_game(self) -> RPGGame:
        assert self._rpg_game is not None
        return self._rpg_game

    @override
    def on_pre_create_game(self) -> None:
        pass

    @override
    def on_post_create_game(self) -> None:
        pass

    @override
    def initialize(self, execution_context: Any) -> None:
        assert isinstance(execution_context, RPGGame)
        assert self._rpg_game is None
        self._rpg_game = execution_context
