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
    WolfKillAction,
)


###############################################################################################################################################
@final
class SocialDeductionWerewolfSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:

        assert self._game._time_marker % 2 == 1, "时间标记必须是奇数，是夜晚"
        logger.info(f"夜晚 {self._game._time_marker // 2 + 1} 开始")
        logger.info("狼人请睁眼，选择你要击杀的玩家")

        # 临时先这么写！
        alive_werewolf_entities = self._game.get_group(
            Matcher(
                all_of=[WerewolfComponent],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        logger.debug(
            f"当前存活的狼人实体 = {[e.name for e in alive_werewolf_entities]}"
        )

        if len(alive_werewolf_entities) == 0:
            logger.warning("当前没有存活的狼人，无法进行击杀")
            return

        alive_town_entities = self._game.get_group(
            Matcher(
                any_of=[
                    SeerComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        logger.debug(f"当前存活的村民实体 = {[e.name for e in alive_town_entities]}")
        if len(alive_town_entities) == 0:
            logger.warning("当前没有存活的村民，无法进行击杀")
            return

        # 从存活的村民中随机选择一个目标
        import random

        target_entity = random.choice(list(alive_town_entities))
        target_entity.replace(
            WolfKillAction,
            target_entity.name,
            "wolf name",
            "reason",
        )

        target_entity.replace(DeathComponent, target_entity.name)

        logger.info(f"狼人击杀了玩家 {target_entity.name}")

    ###############################################################################################################################################
