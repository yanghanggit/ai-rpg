"""战斗结果判定系统: 检测生命值归零、判定胜负、通知战斗结果。"""

from typing import Final, final, override, Set
from loguru import logger
from ..entitas import ExecuteProcessor, Matcher, Entity
from ..game.tcg_game import TCGGame
from ..models import (
    DeathComponent,
    CombatStatsComponent,
    CombatResult,
    AllyComponent,
    EnemyComponent,
)


@final
class CombatOutcomeSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: Final[TCGGame] = game_context

    ########################################################################################################################################################################
    @override
    async def execute(self) -> None:

        # 处理生命值归零的实体
        self._process_zero_health_entities()

        # 判定战斗胜负
        self._determine_combat_winner()

    ########################################################################################################################################################################
    def _process_zero_health_entities(self) -> None:
        """处理生命值归零的实体,为其添加死亡组件。"""
        defeated_entities = self._game.get_group(
            Matcher(all_of=[CombatStatsComponent], none_of=[DeathComponent])
        ).entities.copy()

        for entity in defeated_entities:
            combat_stats_comp = entity.get(CombatStatsComponent)
            if combat_stats_comp.stats.hp <= 0:

                logger.warning(f"{combat_stats_comp.name} is dead")
                self._game.add_human_message(entity, f"""# 通知！你已被击败！""")
                entity.replace(DeathComponent, combat_stats_comp.name)

    ########################################################################################################################################################################
    def _determine_combat_winner(self) -> None:
        """根据双方死亡情况判定战斗胜负。"""
        if not self._game.current_combat_sequence.is_ongoing:
            return  # 不是本阶段就直接返回

        if self._is_ally_side_eliminated():
            self._game.current_combat_sequence.complete_combat(CombatResult.LOSE)
            self._broadcast_result_to_allies(CombatResult.LOSE)
        elif self._is_enemy_side_eliminated():
            self._game.current_combat_sequence.complete_combat(CombatResult.WIN)
            self._broadcast_result_to_allies(CombatResult.WIN)
        else:
            logger.debug("combat continue!!!")

    ########################################################################################################################################################################
    def _is_enemy_side_eliminated(self) -> bool:
        """检查敌方是否全灭。"""
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_on_stage = self._game.get_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        active_enemies: Set[Entity] = set()
        defeated_enemies: Set[Entity] = set()

        for entity in actors_on_stage:

            if not entity.has(EnemyComponent):
                continue

            # 激活的敌人
            active_enemies.add(entity)

            if entity.has(DeathComponent):
                # 已被击败的敌人
                defeated_enemies.add(entity)

        # 判断是否所有敌人都已被击败
        return len(active_enemies) > 0 and len(defeated_enemies) >= len(active_enemies)

    ########################################################################################################################################################################
    def _is_ally_side_eliminated(self) -> bool:
        """检查友方是否全灭。"""

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "Player entity should not be None."

        actors_on_stage = self._game.get_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        current_allies: Set[Entity] = set()
        defeated_allies: Set[Entity] = set()

        for entity in actors_on_stage:

            if not entity.has(AllyComponent):
                continue

            # 当前存活的友方单位
            current_allies.add(entity)

            if entity.has(DeathComponent):
                # 已被击败的友方单位
                defeated_allies.add(entity)

        # 判断是否所有友方单位都已被击败
        return len(current_allies) > 0 and len(defeated_allies) >= len(current_allies)

    ########################################################################################################################################################################
    def _broadcast_result_to_allies(self, result: CombatResult) -> None:
        """向所有友方单位广播战斗结果消息。"""

        player_entity = self._game.get_player_entity()
        assert player_entity is not None, "Player entity should not be None."

        combat_stage_entity = self._game.resolve_stage_entity(player_entity)
        assert (
            combat_stage_entity is not None
        ), "Player's stage entity should not be None."

        actors_on_stage = self._game.get_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        for entity in actors_on_stage:
            if not entity.has(AllyComponent):
                continue

            if result == CombatResult.WIN:
                self._game.add_human_message(
                    entity,
                    f"# 通知！你胜利了！",
                    combat_outcome=combat_stage_entity.name,
                )
            elif result == CombatResult.LOSE:
                self._game.add_human_message(
                    entity,
                    f"# 通知！你失败了！",
                    combat_outcome=combat_stage_entity.name,
                )

    ########################################################################################################################################################################
