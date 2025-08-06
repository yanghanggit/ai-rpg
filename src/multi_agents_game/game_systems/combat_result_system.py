from typing import Set, final, override

from loguru import logger

from ..entitas import Entity, ExecuteProcessor
from ..game.tcg_game import TCGGame
from ..game.tcg_game_context import RetrieveMappingOptions
from ..models import (
    CombatResult,
    DeathComponent,
    HeroComponent,
    MonsterComponent,
)


@final
class CombatResultSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:

        # 检查战斗结果的死亡情况
        if not self._game.current_engagement.is_on_going_phase:
            # 不是本阶段就直接返回
            return

        if self._are_all_heroes_defeated():
            self._game.current_engagement.combat_complete(CombatResult.HERO_LOSE)
            self._notify_combat_result(CombatResult.HERO_LOSE)
        elif self._are_all_monsters_defeated():
            self._game.current_engagement.combat_complete(CombatResult.HERO_WIN)
            self._notify_combat_result(CombatResult.HERO_WIN)
        else:
            logger.debug("combat continue!!!")

    ########################################################################################################################################################################
    def _are_all_monsters_defeated(self) -> bool:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_on_stage = self._game.retrieve_actors_on_stage(
            player_entity, RetrieveMappingOptions(filter_dead_actors=False)
        )
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        active_monsters: Set[Entity] = set()
        defeated_monsters: Set[Entity] = set()

        for entity in actors_on_stage:

            if not entity.has(MonsterComponent):
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

        actors_on_stage = self._game.retrieve_actors_on_stage(
            player_entity, RetrieveMappingOptions(filter_dead_actors=False)
        )
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        active_heroes: Set[Entity] = set()
        defeated_heroes: Set[Entity] = set()

        for entity in actors_on_stage:

            if not entity.has(HeroComponent):
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

        actors_on_stage = self._game.retrieve_actors_on_stage(
            player_entity, RetrieveMappingOptions(filter_dead_actors=False)
        )
        assert len(actors_on_stage) > 0, f"entities with actions: {actors_on_stage}"

        for entity in actors_on_stage:
            if not entity.has(HeroComponent):
                continue

            if result == CombatResult.HERO_WIN:
                self._game.append_human_message(
                    entity,
                    f"你胜利了！",
                    combat_result_tag=player_stage_entity._name,
                )
            elif result == CombatResult.HERO_LOSE:
                self._game.append_human_message(
                    entity,
                    f"你失败了！",
                    combat_result_tag=player_stage_entity._name,
                )

    ########################################################################################################################################################################
