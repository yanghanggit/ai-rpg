from entitas import Context  # type: ignore
from typing import final, Optional
from game.base_game import BaseGame


@final
class TCGGameContext(Context):

    #
    def __init__(
        self,
    ) -> None:
        #
        super().__init__()

        self._game: Optional[BaseGame] = None
