from typing import final, override, Set
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
        self._game: TCGGame = game_context

    ########################################################################################################################################################################
    @override
    async def execute(self) -> None:

        self._check_health_status()

        self._evaluate_outcome()

    ########################################################################################################################################################################
    def _check_health_status(self) -> None:
        # 更新角色的健康状态
        entities = self._game.get_group(
            Matcher(all_of=[CombatStatsComponent], none_of=[DeathComponent])
        ).entities.copy()
        for entity in entities:
            rpg_character_profile_component = entity.get(CombatStatsComponent)
            if rpg_character_profile_component.stats.hp <= 0:
                logger.warning(f"{rpg_character_profile_component.name} is dead")
                self._game.append_human_message(entity, "# 你已被击败！")
                entity.replace(DeathComponent, rpg_character_profile_component.name)

    ########################################################################################################################################################################
    def _evaluate_outcome(self) -> None:

        # 检查战斗结果的死亡情况
        if not self._game.current_engagement.is_ongoing:
            return  # 不是本阶段就直接返回

        if self._are_all_heroes_defeated():
            self._game.current_engagement.complete_combat(CombatResult.HERO_LOSE)
            self._notify_combat_result(CombatResult.HERO_LOSE)
        elif self._are_all_monsters_defeated():
            self._game.current_engagement.complete_combat(CombatResult.HERO_WIN)
            self._notify_combat_result(CombatResult.HERO_WIN)
        else:
            logger.debug("combat continue!!!")

    ########################################################################################################################################################################
    def _are_all_monsters_defeated(self) -> bool:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_on_stage = self._game.get_all_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        active_monsters: Set[Entity] = set()
        defeated_monsters: Set[Entity] = set()

        for entity in actors_on_stage:

            if not entity.has(EnemyComponent):
                continue

            active_monsters.add(entity)
            if entity.has(DeathComponent):
                defeated_monsters.add(entity)

        return len(active_monsters) > 0 and len(defeated_monsters) >= len(
            active_monsters
        )

    ########################################################################################################################################################################
    def _are_all_heroes_defeated(self) -> bool:
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_on_stage = self._game.get_all_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        active_heroes: Set[Entity] = set()
        defeated_heroes: Set[Entity] = set()

        for entity in actors_on_stage:

            if not entity.has(AllyComponent):
                continue

            active_heroes.add(entity)
            if entity.has(DeathComponent):
                defeated_heroes.add(entity)

        return len(active_heroes) > 0 and len(defeated_heroes) >= len(active_heroes)

    ########################################################################################################################################################################
    def _notify_combat_result(self, result: CombatResult) -> None:
        # TODO, 通知战斗结果
        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        player_stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert player_stage_entity is not None

        actors_on_stage = self._game.get_all_actors_on_stage(player_entity)
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        for entity in actors_on_stage:
            if not entity.has(AllyComponent):
                continue

            if result == CombatResult.HERO_WIN:
                self._game.append_human_message(
                    entity,
                    f"你胜利了！",
                    combat_result_tag=player_stage_entity.name,
                )
            elif result == CombatResult.HERO_LOSE:
                self._game.append_human_message(
                    entity,
                    f"你失败了！",
                    combat_result_tag=player_stage_entity.name,
                )

    ########################################################################################################################################################################
