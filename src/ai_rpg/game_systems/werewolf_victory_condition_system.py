# from typing import final
# from overrides import override
# from ..entitas import ExecuteProcessor, Matcher
# from ..game.sdg_game import SDGGame
# from loguru import logger
# from ..models import (
#     WitchComponent,
#     DeathComponent,
#     WerewolfComponent,
#     SeerComponent,
#     VillagerComponent,
# )


# ###############################################################################################################################################
# @final
# class WerewolfVictoryConditionSystem(ExecuteProcessor):

#     ###############################################################################################################################################
#     def __init__(self, game_context: SDGGame) -> None:
#         self._game: SDGGame = game_context

#     ###############################################################################################################################################
#     @override
#     async def execute(self) -> None:
#         logger.info(
#             "==================== WerewolfVictoryConditionSystem 执行 ==================== "
#         )
#         check_town_victory = self.check_town_victory()
#         check_werewolves_victory = self.check_werewolves_victory()

#         if check_town_victory or check_werewolves_victory:

#             # TODO, 临时处理！
#             logger.warning("游戏结束，触发胜利条件，准备终止游戏...")
#             self._game.should_terminate = True

#             ## 随便打印一下！
#             if check_town_victory:
#                 logger.warning("\n!!!!!!!!!!!!!!!!!村民阵营胜利!!!!!!!!!!!!!!!!!!!\n")
#             elif check_werewolves_victory:
#                 logger.warning("\n!!!!!!!!!!!!!!!!!狼人阵营胜利!!!!!!!!!!!!!!!!!!!\n")

#     ################################################################################################################################################

#     ################################################################################################################################################
