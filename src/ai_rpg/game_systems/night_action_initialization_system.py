from typing import final
from overrides import override
from ..entitas import ExecuteProcessor, Matcher
from ..game.sd_game import SDGame
from loguru import logger
from ..models import (
    WerewolfComponent,
    SeerComponent,
    WitchComponent,
    VillagerComponent,
    DeathComponent,
    NightActionReadyComponent,
)


###############################################################################################################################################
@final
class NightActionInitializationSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: SDGame) -> None:
        self._game: SDGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        night_phase_action_entities = self._game.get_group(
            Matcher(
                all_of=[NightActionReadyComponent],
            )
        ).entities.copy()

        if len(night_phase_action_entities) > 0:
            logger.debug("已有玩家选择夜晚行动，跳过自动添加")
            return

        # 自动为存活的预言家添加夜晚行动
        logger.debug("自动为存活的玩家添加夜晚行动")

        alive_player_entities = self._game.get_group(
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

        for entity in alive_player_entities:
            entity.replace(NightActionReadyComponent, entity.name)

    ###############################################################################################################################################
