from loguru import logger
from entitas import ExecuteProcessor  # type: ignore
from overrides import override
from typing import final
from components.components_v_0_0_1 import (
    StagePermitComponent,
    StageComponent,
    StageEnvironmentComponent,
)

from game.tcg_game import TCGGame


#######################################################################################################################################
@final
class HomeStagePermitSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        player_stage = self._game.safe_get_stage_entity(player_entity)
        assert player_stage is not None

        # StageEnvironmentComponent
        stage_evironment_comp = player_stage.get(StageEnvironmentComponent)
        if stage_evironment_comp.narrate != "":
            # 说明已经有环境描述了。
            logger.debug(
                f"HomeStagePermitSystem: StageEnvironmentComponent: {stage_evironment_comp.narrate}，目前不需要再词推理了。"
            )
            return

        player_stage.replace(
            StagePermitComponent,
            player_stage.get(StageComponent).name,
        )

    #######################################################################################################################################
