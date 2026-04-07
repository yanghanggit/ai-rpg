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
from ..models import BlockComponent, DungeonComponent, IdentityComponent, Round


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
        game: TCGGame,
        strategy: ActionOrderStrategy = ActionOrderStrategy.RANDOM,
    ) -> None:
        self._game: Final[TCGGame] = game
        self._strategy: Final[ActionOrderStrategy] = strategy

    ############################################################################################################
    @override
    async def execute(self) -> None:
        """
        编排骨架：依次调用「清除旧回合状态」与「创建新回合」。
        两个子函数各自持有完整的状态守护，execute 无需额外判断。
        """
        self._clear_previous_round_state()
        self._create_next_round()

    ############################################################################################################
    def _clear_previous_round_state(self) -> None:
        """清除上一回合的手牌与格挡状态。

        内部状态守护（不满足则静默返回）：
        - 状态为 NONE / INITIALIZATION → 战斗尚未进入有效阶段，无需清除
        - 尚无任何回合 → 不存在「上一回合」，无状态可清
        - 最新回合未完成 → 状态仍在使用中，不清除
        """
        valid_state = (
            self._game.current_dungeon.is_ongoing
            or self._game.current_dungeon.is_combat_completed
            or self._game.current_dungeon.is_post_combat
        )

        if not valid_state:
            logger.debug(
                "当前战斗状态非 ONGOING/COMPLETE/POST_COMBAT，跳过旧回合状态清除"
            )
            return

        current_rounds = self._game.current_dungeon.current_rounds or []
        if len(current_rounds) == 0:
            return

        last_round = self._game.current_dungeon.latest_round
        assert last_round is not None, "latest_round is None"
        if not last_round.is_round_completed:
            return

        logger.debug("清除旧回合手牌与格挡状态")
        self._game.clear_round_state()

    ############################################################################################################
    def _create_next_round(self) -> None:
        """创建并初始化下一个战斗回合。

        内部状态守护（不满足则静默返回）：
        - 战斗未进行中 → 跳过
        - 已有回合且最新回合未完成 → 等待，跳过
        """
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

    ############################################################################################################
