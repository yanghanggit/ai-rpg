"""战斗回合完成判定系统

职责：
- 在每次 pipeline 执行时判断当前回合是否结束
- 判断依据：所有存活角色的 RoundStatsComponent.energy <= 0（或无该组件）
- 满足条件时写入 Round.is_completed = True

设计说明：
- energy-based 判断反映运行时真实剩余行动数，比结构性计数（completed_actors/action_order）更准确
- 位于 StagePostArbitrationActionSystem 之后，确保本轮所有 energy 消耗已结算
- 位于 CombatOutcomeSystem 之前，使战斗结果检查能感知到回合完成状态
- init round（action_order=[]）跳过判断，维持初始化阶段行为
"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import RoundStatsComponent


###############################################################################################################################################
@final
class CombatRoundCompletionSystem(ExecuteProcessor):
    """战斗回合完成判定系统

    在每次 pipeline 执行时检查当前回合是否应标记为完成。
    当本场景内所有存活角色均无剩余行动力（energy <= 0 或无 RoundStatsComponent）时，
    将最新回合的 is_completed 置为 True。

    执行时机：
    - StagePostArbitrationActionSystem 之后（所有出牌 energy 消耗已结算）
    - CombatOutcomeSystem 之前（战斗结果检查依赖 is_completed 状态）
    """

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # 守卫①：战斗未进行中 → 跳过
        if not self._game.current_dungeon.is_ongoing:
            return

        latest_round = self._game.current_dungeon.latest_round
        assert latest_round is not None, "latest_round is None"

        # 守卫②：无回合，或回合已标记完成 → 跳过
        if latest_round is None or latest_round.is_completed:
            return

        # 守卫③：init round（无快照） → 跳过
        if not latest_round.actor_order_snapshots:
            return

        # 获取本场景所有存活角色
        player_entity = self._game.get_player_entity()
        if player_entity is None:
            return
        actors_in_stage = self._game.get_alive_actors_in_stage(player_entity)

        # 判断：所有存活角色均无剩余行动力
        all_energy_exhausted = all(
            not actor.has(RoundStatsComponent)
            or actor.get(RoundStatsComponent).energy <= 0
            for actor in actors_in_stage
        )

        if all_energy_exhausted:
            latest_round.is_completed = True
            logger.info(
                f"回合完成：所有存活角色 energy 耗尽，is_completed = True"
                f"（actor_order_snapshots={latest_round.actor_order_snapshots}）"
            )
