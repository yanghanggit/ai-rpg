from typing import final
from overrides import override
from ..entitas import ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from loguru import logger
from ..models import (
    WitchComponent,
    DeathComponent,
    WerewolfComponent,
    SeerComponent,
    VillagerComponent,
)


###############################################################################################################################################
@final
class WerewolfVictoryConditionSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        logger.info(
            "==================== WerewolfVictoryConditionSystem 执行 ==================== "
        )
        check_town_victory = self._check_town_victory()
        check_werewolves_victory = self._check_werewolves_victory()

        if check_town_victory or check_werewolves_victory:

            # TODO, 临时处理！
            self._game.should_terminate = True

            ## 随便打印一下！
            if check_town_victory:
                logger.warning("\n!!!!!!!!!!!!!!!!!村民阵营胜利!!!!!!!!!!!!!!!!!!!\n")
            elif check_werewolves_victory:
                logger.warning("\n!!!!!!!!!!!!!!!!!狼人阵营胜利!!!!!!!!!!!!!!!!!!!\n")

    ################################################################################################################################################
    # 判断村民阵营胜利：所有狼人都被淘汰且至少有一个村民存活
    def _check_town_victory(self) -> bool:
        dead_werewolves = self._game.get_group(
            Matcher(
                all_of=[WerewolfComponent, DeathComponent],
            )
        ).entities.copy()

        total_werewolves = self._game.get_group(
            Matcher(
                all_of=[WerewolfComponent],
            )
        ).entities.copy()

        alive_town_folks = self._game.get_group(
            Matcher(
                any_of=[
                    VillagerComponent,
                    SeerComponent,
                    WitchComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        # 村民胜利条件：所有狼人都死亡 且 至少有一个村民存活
        return len(alive_town_folks) > 0 and len(dead_werewolves) >= len(
            total_werewolves
        )

    ################################################################################################################################################
    # 判断狼人阵营胜利：狼人数量大于等于村民数量且至少有一个狼人存活
    def _check_werewolves_victory(self) -> bool:

        alive_town_folks = self._game.get_group(
            Matcher(
                any_of=[
                    VillagerComponent,
                    SeerComponent,
                    WitchComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        alive_werewolves = self._game.get_group(
            Matcher(
                all_of=[WerewolfComponent],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        # 狼人胜利条件：狼人数量 >= 村民数量 且 至少有一个狼人存活
        return (
            len(alive_town_folks) <= len(alive_werewolves) and len(alive_werewolves) > 0
        )

    ################################################################################################################################################
