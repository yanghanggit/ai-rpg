"""
战斗回合开始系统
"""

from enum import StrEnum, unique
import random
from typing import Dict, Final, List, Set, final, override
from loguru import logger
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import get_alive_actors_in_stage
from ..game.dbg_combat_processor import get_energy
from ..models import (
    CharacterStatsComponent,
    DeathComponent,
    # DEFAULT_ROUND_ENERGY,
    DrawCardsAction,
    DungeonComponent,
    IdentityComponent,
    Round,
    RoundStatsComponent,
)


###############################################################################################################################################
# 行动顺序策略枚举
@final
@unique
class ActionOrderStrategy(StrEnum):
    """战斗回合中角色行动顺序的排序策略"""

    RANDOM = "random"  # 随机打乱（默认）
    CREATION_ORDER = "creation_order"  # 按实体创建顺序（creation_order 小的靠前）


@final
class CombatRoundStartSystem(ReactiveProcessor):
    """
    战斗回合开始系统：监听 DrawCardsAction，在需要时创建并开启新回合。

    必须在 DrawCardsActionSystem 之前注册（顺序即因果链：先开回合，后抓牌）。
    """

    ############################################################################################################
    def __init__(
        self,
        game: DBGGame,
        strategy: ActionOrderStrategy = ActionOrderStrategy.RANDOM,
    ) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._strategy: Final[ActionOrderStrategy] = strategy

    ############################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        """监听 DrawCardsAction 的添加事件，作为创建新回合的唯一触发源。"""
        return {Matcher(DrawCardsAction): GroupEvent.ADDED}

    ############################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(DrawCardsAction)

    ############################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        logger.debug(
            f"CombatRoundStartSystem: 收到 {len(entities)} 个 DrawCardsAction 实体"
        )

        # 状态守卫①：战斗未进行中 → 静默跳过
        if not self._game.current_dungeon_combat_room.combat.is_ongoing:
            logger.debug("当前战斗状态非 ONGOING，跳过回合创建")
            return

        # 状态守卫②：已有进行中的回合（未完成）→ 不重复创建
        latest_round = self._game.current_dungeon_combat_room.combat.latest_round
        if latest_round is not None and not latest_round.is_completed:
            logger.debug("当前已有未完成回合，跳过回合创建")
            return

        logger.debug("DrawCardsAction 触发，开始创建新回合...")

        # 玩家角色
        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "player_entity is None"

        # 所有存活角色
        actors_in_stage = get_alive_actors_in_stage(self._game, player_entity)
        assert len(actors_in_stage) > 0, "actors_in_stage is empty"
        for actor in actors_in_stage:
            assert actor.has(
                CharacterStatsComponent
            ), f"actor {actor.name} 缺少 CharacterStatsComponent"
            assert actor.has(
                IdentityComponent
            ), f"actor {actor.name} 缺少 IdentityComponent"

        # 当前舞台（必须是副本）
        stage_entity = self._game.resolve_stage_entity(player_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert stage_entity.has(DungeonComponent), "stage_entity 没有 DungeonComponent"

        round_number = len(self._game.current_dungeon_combat_room.combat.rounds) + 1
        new_round = self._start_new_round(actors_in_stage)

        # 快照必须在 start_new_round 之后构建，此时 RoundStatsComponent 已按新回合重置
        if self._strategy == ActionOrderStrategy.RANDOM:
            snapshot_entities = self._shuffled_actors_by_round(actors_in_stage)
        else:  # CREATION_ORDER（含未知策略回退）
            snapshot_entities = self._sorted_actors_by_creation_order(actors_in_stage)

        new_round.action_order = [entity.name for entity in snapshot_entities]
        new_round.current_actor = (
            snapshot_entities[0].name if snapshot_entities else None
        )
        logger.debug(f"设置当前 turn 行动角色: {new_round.current_actor}")
        logger.info(f"创建第 {round_number} 回合，行动顺序: {new_round.action_order}")

    ############################################################################################################
    def _start_new_round(self, actors: set[Entity]) -> Round:
        """创建并追加新回合，同时重置所有参战角色的 RoundStatsComponent。"""
        assert (
            self._game.current_dungeon_combat_room.combat.is_ongoing
        ), "当前战斗未进行中，无法开始新回合"

        # 守卫：若当前已有回合，则必须确保上一回合已完成
        current_rounds = self._game.current_dungeon_combat_room.combat.rounds or []
        if len(current_rounds) > 0:
            last_round = self._game.current_dungeon_combat_room.combat.latest_round
            assert last_round is not None, "latest_round is None"
            assert last_round.is_completed, "上一回合尚未完成，无法创建新回合"

        # 创建新回合并追加到当前战斗
        new_round = Round()
        self._game.current_dungeon_combat_room.combat.rounds.append(new_round)

        # 重置所有参战角色的 RoundStatsComponent
        for actor in actors:
            assert not actor.has(
                RoundStatsComponent
            ), f"{actor.name} 已存在 RoundStatsComponent"
            assert not actor.has(DeathComponent), f"{actor.name} 已死亡，不应参与新回合"
            actor.replace(RoundStatsComponent, actor.name, 2)

        return new_round

    ############################################################################################################
    def _shuffled_actors_by_round(self, actors: Set[Entity]) -> List[Entity]:
        """从给定的角色集合中，筛选本回合仍有行动力的角色并随机打乱顺序。"""
        eligible: List[Entity] = [entity for entity in actors if get_energy(entity) > 0]
        random.shuffle(eligible)
        return eligible

    ############################################################################################################
    def _sorted_actors_by_creation_order(self, actors: Set[Entity]) -> List[Entity]:
        """从给定的角色集合中，筛选本回合仍有行动力的角色并按创建顺序升序排列。"""
        eligible: List[Entity] = [entity for entity in actors if get_energy(entity) > 0]
        eligible.sort(key=lambda entity: entity.get(IdentityComponent).creation_order)
        return eligible

    ################################################################################################################
