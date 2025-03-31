from loguru import logger
from entitas import ExecuteProcessor, Matcher  # type: ignore
from overrides import override
from typing import final
from components.components_v_0_0_1 import (
    StagePermitComponent,
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
        # 清理所有的 StagePermitComponent
        self._clear_permit()
        # 重新添加
        self._add_permit()

    #######################################################################################################################################
    def _clear_permit(self) -> None:
        stage_entities = self._game.get_group(
            Matcher(
                all_of=[
                    StagePermitComponent,
                ]
            )
        ).entities.copy()
        for entity in stage_entities:
            logger.debug(
                f"HomeStagePermitSystem: StagePermitComponent: {entity._name}，清除 StagePermitComponent。"
            )
            entity.remove(StagePermitComponent)

    #######################################################################################################################################
    def _add_permit(
        self,
    ) -> None:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        player_stage = self._game.safe_get_stage_entity(player_entity)
        assert player_stage is not None

        stage_evironment_comp = player_stage.get(StageEnvironmentComponent)
        if stage_evironment_comp.narrate != "":
            # 说明已经有环境描述了。
            logger.debug(
                f"HomeStagePermitSystem: StageEnvironmentComponent 目前不需要再词推理了: {stage_evironment_comp.narrate}"
            )
            return

        player_stage.replace(
            StagePermitComponent,
            player_stage._name,
        )

    #######################################################################################################################################
