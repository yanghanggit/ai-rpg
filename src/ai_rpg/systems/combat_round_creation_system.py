"""
战斗回合创建系统

职责：
- 检查战斗状态
- 判断是否需要创建新回合
- 生成并初始化回合的 action_order

设计特点：
- 使用 ExecuteProcessor，每次 pipeline 执行时主动检查
- 避免重复创建（第一回合已在 CombatInitializationSystem 中创建）
- 为后续系统（EnemyDrawDecisionSystem）提供 action_order 上下文
"""

from typing import Final, final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame


@final
class CombatRoundCreationSystem(ExecuteProcessor):
    """
    战斗回合创建系统

    在每次 pipeline 执行时检查是否需要创建新回合。
    确保 EnemyDrawDecisionSystem 等后续系统可以访问最新的 action_order。

    执行时机：
    - 在 CombatInitializationSystem 之后（第一回合已创建）
    - 在 EnemyDrawDecisionSystem 之前（决策需要 action_order）
    """

    def __init__(self, game_context: TCGGame) -> None:
        self._game: Final[TCGGame] = game_context

    @override
    async def execute(self) -> None:
        """
        检查并创建新回合

        执行逻辑：
        1. 检查战斗是否进行中
        2. 检查是否有回合存在（第一回合由本系统创建）
        3. 检查上一回合是否完成
        4. 创建新回合并生成 action_order
        """
        # 检查战斗状态
        if not self._game.current_combat_sequence.is_ongoing:
            # 战斗未进行中，跳过回合创建
            return

        # 检查是否有回合存在（第一回合创建）
        if len(self._game.current_combat_sequence.current_rounds) == 0:
            logger.info("战斗开始，创建第一回合")
            new_round = self._game.create_next_round()
            if new_round:
                logger.info(f"创建第 1 回合，行动顺序: {new_round.action_order}")
            else:
                logger.error("创建第一回合失败")
            return

        # 检查上一回合是否完成
        last_round = self._game.current_combat_sequence.latest_round
        if last_round.is_completed:
            logger.debug(f"上一回合已完成，创建新回合")
            new_round = self._game.create_next_round()
            if new_round:
                logger.info(
                    f"创建第 {len(self._game.current_combat_sequence.current_rounds)} 回合，"
                    f"行动顺序: {new_round.action_order}"
                )
            else:
                logger.error("创建新回合失败")
