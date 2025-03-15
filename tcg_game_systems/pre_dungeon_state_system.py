from entitas import ExecuteProcessor, Matcher  # type: ignore
from typing import final, override
from game.tcg_game import TCGGame
from components.components import EnterStageFlagComponent
from components.actions2 import StatusUpdateAction, DEFAULT_NULL_ACTION


@final
class PreDungeonStateSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    @override
    def execute(self) -> None:

        entities = self._game.get_group(
            Matcher(
                all_of=[
                    EnterStageFlagComponent,
                ],
            )
        ).entities.copy()

        # 这个pass，添加动作。
        for entity1 in entities:
            # 添加这个动作。
            assert not entity1.has(StatusUpdateAction)
            entity1.replace(StatusUpdateAction, DEFAULT_NULL_ACTION)
