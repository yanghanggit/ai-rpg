"""战斗回合完成判定系统"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import get_alive_actors_in_stage


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
        if not self._game.current_combat_room.combat.is_ongoing:
            return

        latest_round = self._game.current_combat_room.combat.latest_round

        # 守卫②：无回合，或回合已标记完成 → 跳过
        if latest_round is None or latest_round.is_completed:
            return

        # 守卫③：init round（无行动顺序） → 跳过
        if not latest_round.action_order:
            return

        # 获取本场景所有存活角色
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "player_entity is None"

        # 获取本场景所有存活角色（不包括已死亡的角色）
        actors_in_stage = get_alive_actors_in_stage(self._game, player_entity)

        # 判断：所有存活角色均已 pass turn（completed_actors 是行动权推进的唯一依据，
        # 与 energy 是否耗尽无关；死亡角色已被 get_alive_actors_in_stage 过滤，不会阻塞回合结束）
        completed = set(latest_round.completed_actors)
        all_passed = all(actor.name in completed for actor in actors_in_stage)

        if all_passed:
            latest_round.is_completed = True
            logger.info(
                f"回合完成：所有存活角色均已 pass turn，is_completed = True"
                f"（action_order={latest_round.action_order}）"
            )
