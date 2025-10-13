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
    SeerCheckAction,
)


###############################################################################################################################################
@final
class SocialDeductionSeerSystem(ExecuteProcessor):

    ###############################################################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ###############################################################################################################################################
    @override
    async def execute(self) -> None:
        assert self._game._time_marker % 2 == 1, "时间标记必须是奇数，是夜晚"
        logger.info(f"夜晚 {self._game._time_marker // 2 + 1} 开始")
        logger.info("预言家请睁眼，选择你要查看的玩家")

        # 临时先这么写！
        alive_seer_entities = self._game.get_group(
            Matcher(
                all_of=[SeerComponent],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        if len(alive_seer_entities) == 0:
            logger.warning("当前没有存活的狼人，无法进行击杀")
            return

        assert len(alive_seer_entities) == 1, "预言家不可能有多个"
        seer_entity = next(iter(alive_seer_entities))
        assert seer_entity is not None, "预言家实体不可能为空"

        logger.debug(f"当前预言家实体 = {seer_entity.name}")

        alive_player_entities = self._game.get_group(
            Matcher(
                any_of=[
                    WerewolfComponent,
                    WitchComponent,
                    VillagerComponent,
                ],
                none_of=[DeathComponent],
            )
        ).entities.copy()

        logger.debug(f"当前存活的玩家实体 = {[e.name for e in alive_player_entities]}")

        # 从存活的村民中随机选择一个目标
        import random

        target_entity = random.choice(list(alive_player_entities))
        target_entity.replace(
            SeerCheckAction,
            target_entity.name,
            seer_entity.name,
        )

        logger.info(f"预言家查看了玩家 {target_entity.name}")

        if target_entity.has(WerewolfComponent):
            logger.info(f"预言家查看的玩家 {target_entity.name} 是 狼人")
            self._game.append_human_message(
                seer_entity,
                f"# 提示！你查看了玩家 {target_entity.name} 的身份，结论：{target_entity.name} 是 狼人",
            )
        else:
            logger.info(f"预言家查看的玩家 {target_entity.name} 不是 狼人")
            self._game.append_human_message(
                seer_entity,
                f"# 提示！你查看了玩家 {target_entity.name} 的身份，结论：{target_entity.name} 不是 狼人",
            )

    ###############################################################################################################################################
