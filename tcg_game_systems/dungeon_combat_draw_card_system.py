from entitas import ExecuteProcessor  # type: ignore
from models_v_0_0_1 import (
    DungeonComponent,
)
from typing import final, override
from game.tcg_game import TCGGame
from tcg_game_systems.draw_cards_utils import DrawCardsUtils


#######################################################################################################################################
@final
class DungeonCombatDrawCardSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        pass

    #######################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        if not self._game.current_engagement.is_on_going_phase:
            return  # 不是本阶段就直接返回

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert stage_entity is not None
        assert stage_entity.has(DungeonComponent)
        actors_on_stage = self._game.retrieve_actors_on_stage(player_entity)
        if len(actors_on_stage) == 0:
            return

        draw_card_utils = DrawCardsUtils(self._game, actors_on_stage)
        await draw_card_utils.draw_cards()

    #######################################################################################################################################
