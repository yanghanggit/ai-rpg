"""战斗状态转换系统：战斗结束后将战斗状态从 COMPLETE 转换为 POST_COMBAT。"""

from typing import Final, final

from loguru import logger
from overrides import override

from ..entitas import ExecuteProcessor
from ..game.dbg_game import DBGGame


#######################################################################################################################################
@final
class CombatPostCombatTransitionSystem(ExecuteProcessor):
    """战斗结束后转换战斗状态：COMPLETE -> POST_COMBAT。"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        """每帧检查战斗是否结束；结束则将战斗状态转换为战后阶段。"""

        combat = self._game.current_dungeon_combat_room.combat
        if not combat.is_combat_completed:
            # 战斗未结束（或已处于战后阶段），无需转换。
            return

        assert combat.is_won or combat.is_lost, "战斗结果状态异常！"

        logger.info("战斗结束，转换战斗状态：COMPLETE -> POST_COMBAT")
        combat.transition_to_post_combat()


#######################################################################################################################################
