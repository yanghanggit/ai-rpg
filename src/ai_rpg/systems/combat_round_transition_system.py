"""
战斗回合过渡系统

职责：
- 判断是否需要创建新回合并生成 action_order

设计特点：
- 使用 ExecuteProcessor，每次 pipeline 执行时主动检查（位于 pipeline 末端）
- 避免重复创建（第一回合已在 CombatInitializationSystem 中创建）
- 为后续系统（EnemyDrawDecisionSystem）提供 action_order 上下文
- 旧回合清理由 CombatRoundCleanupSystem 负责（位于本系统之前）
"""

from enum import StrEnum, unique
import random
from typing import Final, List, Set, final, override
from loguru import logger
from ..entitas import Entity, ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import (
    BlockComponent,
    DungeonComponent,
    IdentityComponent,
    Round,
)


###############################################################################################################################################
# 行动顺序策略枚举
@final
@unique
class ActionOrderStrategy(StrEnum):
    """战斗回合中角色行动顺序的排序策略"""

    RANDOM = "random"  # 随机打乱（默认）
    CREATION_ORDER = "creation_order"  # 按实体创建顺序（creation_order 小的靠前）
    # ⚠️ 测试用：每人出牌 2 次（后续移除）
    # 已知问题：Round.is_round_completed 用 set() 比较，第一轮结束后即判定完成；
    # play_cards_action_system 有 `if name not in completed_actors` 去重保护，第二次出牌不被记录；
    # dungeon_actions.activate_play_cards_specified 的 next_actor 查找也用 set 语义跳过已完成者。
    # 结论：当前 Round/系统 模型 **无法直接支持** 重复名称的 action_order，需配套修改才能生效。
    DOUBLE_ACTION = (
        "double_action"  # 【测试】每人行动 2 次（action_order 中每个名称重复）
    )


@final
class CombatRoundTransitionSystem(ExecuteProcessor):
    """
    战斗回合过渡系统

    在每次 pipeline 执行时创建新的战斗回合。
    旧回合清理由 CombatRoundCleanupSystem 负责（位于本系统之前）。
    位于 combat pipeline 末端，确保下一次 pipeline 执行时新回合已就绪。

    执行时机：
    - 在 CombatRoundCleanupSystem 之后（旧回合已清理）
    - 在 EnemyDrawDecisionSystem 之前（决策需要 action_order）

    行动顺序策略：
    - RANDOM（默认）：每回合随机打乱角色顺序，增加战斗不确定性
    - CREATION_ORDER：按实体创建顺序（creation_order 小的靠前），保证固定顺序

    使用示例：
        # 使用随机策略（默认）
        system = CombatRoundTransitionSystem(game)

        # 使用创建顺序策略
        system = CombatRoundTransitionSystem(
            game,
            strategy=ActionOrderStrategy.CREATION_ORDER
        )
    """

    ############################################################################################################
    def __init__(
        self,
        game: TCGGame,
        strategy: ActionOrderStrategy = ActionOrderStrategy.RANDOM,
    ) -> None:
        self._game: Final[TCGGame] = game
        self._strategy: Final[ActionOrderStrategy] = strategy

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # 状态守护：战斗未进行中 / 最新回合未完成 → 静默跳过
        if not self._game.current_dungeon.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过回合创建")
            return

        logger.debug("检查战斗回合状态，判断是否需要创建新回合...")

        current_rounds = self._game.current_dungeon.current_rounds or []

        if len(current_rounds) > 0:
            last_round = self._game.current_dungeon.latest_round
            assert last_round is not None
            if not last_round.is_round_completed:
                return

        # 玩家角色
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "player_entity is None"

        # 所有存活角色
        actors_in_stage = self._game.get_alive_actors_in_stage(player_entity)
        assert len(actors_in_stage) > 0, "actors_in_stage is empty"

        # 当前舞台（必须是地下城）
        stage_entity = self._game.resolve_stage_entity(player_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert stage_entity.has(DungeonComponent), "stage_entity 没有 DungeonComponent"

        # 根据策略排序角色行动顺序
        if self._strategy == ActionOrderStrategy.RANDOM:
            sorted_actors = self._sort_actors_random(actors_in_stage)
        elif self._strategy == ActionOrderStrategy.CREATION_ORDER:
            sorted_actors = self._sort_actors_by_creation_order(actors_in_stage)
        elif self._strategy == ActionOrderStrategy.DOUBLE_ACTION:
            sorted_actors = self._sort_actors_random(actors_in_stage)
        else:
            logger.warning(f"未知的行动顺序策略: {self._strategy}，使用随机策略")
            sorted_actors = self._sort_actors_random(actors_in_stage)

        # 构造 action_order
        if self._strategy == ActionOrderStrategy.DOUBLE_ACTION:
            # ⚠️ 测试用：每人出现 2 次，暴露当前系统对重复名称的处理缺陷
            single_pass = [entity.name for entity in sorted_actors]
            action_order = single_pass + single_pass
        else:
            action_order = [entity.name for entity in sorted_actors]

        round_number = len(current_rounds) + 1
        new_round = Round(action_order=action_order)
        self._game.current_dungeon.current_combat.rounds.append(new_round)  # type: ignore[union-attr]

        # 每回合开始时重置所有参战角色的 BlockComponent（杀戮尖塔模式：每轮格挡清零）
        for actor in sorted_actors:
            actor.replace(BlockComponent, actor.name, 0)

        logger.info(f"创建第 {round_number} 回合，行动顺序: {new_round.action_order}")

    ############################################################################################################
    def _sort_actors_random(self, actors: Set[Entity]) -> List[Entity]:
        """随机打乱角色顺序

        Args:
            actors: 角色实体集合

        Returns:
            随机排序后的角色实体列表
        """
        shuffled = list(actors)
        random.shuffle(shuffled)
        return shuffled

    ############################################################################################################
    def _sort_actors_by_creation_order(self, actors: Set[Entity]) -> List[Entity]:
        """按实体创建顺序排序（creation_order 小的靠前）

        Args:
            actors: 角色实体集合

        Returns:
            按创建顺序排序的角色实体列表
        """
        return sorted(
            actors,
            key=lambda entity: entity.get(IdentityComponent).creation_order,
        )

    ################################################################################################################
