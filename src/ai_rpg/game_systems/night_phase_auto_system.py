from typing import final
from overrides import override
from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from loguru import logger
from ..models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    DeathComponent,
    NightPhaseAction,
)


###############################################################################################################################################
@final
class NightPhaseAutoSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        logger.info(
            f"夜晚 {self._game._time_marker // 2 + 1} 开始, time_marker: {self._game._time_marker}"
        )

        night_phase_action_entities = self._game.get_group(
            Matcher(
                all_of=[NightPhaseAction],
            )
        ).entities.copy()

        if len(night_phase_action_entities) > 0:
            logger.debug("已有玩家选择夜晚行动，跳过自动添加")
            return

        # 自动为存活的预言家添加夜晚行动
        self._auto_add_night_phase_action()

    ###############################################################################################################################################
    def _auto_add_night_phase_action(self) -> None:
        logger.debug("自动为存活的预言家添加夜晚行动")

        alive_werewolf_player_entities = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        for entity in alive_werewolf_player_entities:
            entity.replace(NightPhaseAction, entity.name)

    ###############################################################################################################################################
