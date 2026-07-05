"""战斗回合完成判定系统"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_entity_ops import get_energy


###############################################################################################################################################
@final
class CombatRoundCompletionSystem(ExecuteProcessor):
    """战斗回合完成判定系统"""

    def __init__(self, game: DBGGame) -> None:
        self._game: Final[DBGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # 守卫①：战斗未进行中 → 跳过
        if not self._game.current_dungeon.is_ongoing:
            return

        latest_round = self._game.current_dungeon.latest_round

        # 守卫②：无回合，或回合已标记完成 → 跳过
        if latest_round is None or latest_round.is_completed:
            return

        # 守卫③：init round（无快照） → 跳过
        if not latest_round.actor_order_snapshots:
            return

        # 获取本场景所有存活角色
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "player_entity is None"
        # if player_entity is None:
        #     return
        actors_in_stage = self._game.get_alive_actors_in_stage(player_entity)

        # 判断：所有存活角色均无剩余行动力
        all_energy_exhausted = all(get_energy(actor) <= 0 for actor in actors_in_stage)

        if all_energy_exhausted:
            latest_round.is_completed = True
            logger.info(
                f"回合完成：所有存活角色 energy 耗尽，is_completed = True"
                f"（actor_order_snapshots={latest_round.actor_order_snapshots}）"
            )
