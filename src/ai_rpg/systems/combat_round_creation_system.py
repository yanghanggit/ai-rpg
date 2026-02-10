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

from enum import StrEnum, unique
import random
from typing import Final, List, Set, final, override
from loguru import logger
from ..entitas import Entity, ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..models import DungeonComponent, IdentityComponent, Round


###############################################################################################################################################
# 行动顺序策略枚举
@final
@unique
class ActionOrderStrategy(StrEnum):
    """战斗回合中角色行动顺序的排序策略"""

    RANDOM = "random"  # 随机打乱（默认）
    CREATION_ORDER = "creation_order"  # 按实体创建顺序（creation_order 小的靠前）


@final
class CombatRoundCreationSystem(ExecuteProcessor):
    """
    战斗回合创建系统

    在每次 pipeline 执行时检查是否需要创建新回合。
    确保 EnemyDrawDecisionSystem 等后续系统可以访问最新的 action_order。

    执行时机：
    - 在 CombatInitializationSystem 之后（第一回合已创建）
    - 在 EnemyDrawDecisionSystem 之前（决策需要 action_order）

    行动顺序策略：
    - RANDOM（默认）：每回合随机打乱角色顺序，增加战斗不确定性
    - CREATION_ORDER：按实体创建顺序（creation_order 小的靠前），保证固定顺序

    使用示例：
        # 使用随机策略（默认）
        system = CombatRoundCreationSystem(game)

        # 使用创建顺序策略
        system = CombatRoundCreationSystem(
            game,
            strategy=ActionOrderStrategy.CREATION_ORDER
        )
    """

    ############################################################################################################
    def __init__(
        self,
        game_context: TCGGame,
        strategy: ActionOrderStrategy = ActionOrderStrategy.RANDOM,
    ) -> None:
        self._game: Final[TCGGame] = game_context
        self._strategy: Final[ActionOrderStrategy] = strategy

    ############################################################################################################
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
            new_round = self._create_next_round()
            logger.info(f"创建第 1 回合，行动顺序: {new_round.action_order}")
            return

        # 检查上一回合是否完成
        last_round = self._game.current_combat_sequence.latest_round
        if last_round.is_completed:
            logger.debug(f"上一回合已完成，创建新回合")
            new_round = self._create_next_round()
            logger.info(
                f"创建第 {len(self._game.current_combat_sequence.current_rounds)} 回合，"
                f"行动顺序: {new_round.action_order}"
            )

    ############################################################################################################
    def _create_next_round(self) -> Round:
        """创建并初始化下一个战斗回合

        前置条件（由 execute 方法保证）：
        - 战斗必须处于 ONGOING 状态
        - 如果已有回合，上一回合必须已完成

        Returns:
            创建的回合对象
        """
        # 前置条件断言
        assert self._game.current_combat_sequence.is_ongoing, "战斗未进行中"
        assert (
            len(self._game.current_combat_sequence.current_rounds) == 0
            or self._game.current_combat_sequence.latest_round.is_completed
        ), "上一回合未完成"

        # 玩家角色
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "player_entity is None"

        # 所有角色
        actors_on_stage = self._game.get_alive_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0, "actors_on_stage is empty"

        # 当前舞台(必然是地下城！)
        stage_entity = self._game.resolve_stage_entity(player_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert stage_entity.has(DungeonComponent), "stage_entity 没有 DungeonComponent"

        # 根据配置的策略排序角色行动顺序
        if self._strategy == ActionOrderStrategy.RANDOM:
            sorted_actors = self._sort_actors_random(actors_on_stage)
        elif self._strategy == ActionOrderStrategy.CREATION_ORDER:
            sorted_actors = self._sort_actors_by_creation_order(actors_on_stage)
        else:
            logger.warning(f"未知的行动顺序策略: {self._strategy}，使用随机策略")
            sorted_actors = self._sort_actors_random(actors_on_stage)

        # 设置回合的环境描写
        action_order = [entity.name for entity in sorted_actors]
        round = Round(
            action_order=action_order,
        )
        self._game.current_combat_sequence.current_combat.rounds.append(round)
        return round

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

    ############################################################################################################
