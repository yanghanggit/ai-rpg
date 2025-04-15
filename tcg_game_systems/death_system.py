from loguru import logger
from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from typing import Set, final, override
from models_v_0_0_1 import (
    DestroyComponent,
    DeathComponent,
    CombatResult,
    RPGCharacterProfileComponent,
    HeroComponent,
    MonsterComponent,
)
from game.tcg_game import TCGGame


@final
class DeathSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:

        # 处理hp为0的情况
        self._update_entities_to_dead_state()

        # 添加销毁
        self._add_destroyed_monster_entities()

        # 检查战斗结果的死亡情况
        self._check_combat_result()

    ########################################################################################################################################################################
    def _update_entities_to_dead_state(self) -> None:
        entities = self._game.get_group(
            Matcher(all_of=[RPGCharacterProfileComponent], none_of=[DeathComponent])
        ).entities.copy()
        for entity in entities:
            rpg_character_profile_component = entity.get(RPGCharacterProfileComponent)
            if rpg_character_profile_component.rpg_character_profile.hp <= 0:
                logger.debug(f"{rpg_character_profile_component.name} is dead")
                self._game.append_human_message(entity, "# 你已被击败！")
                entity.replace(DeathComponent, rpg_character_profile_component.name)

    ########################################################################################################################################################################
    def _add_destroyed_monster_entities(self) -> None:
        entities = self._game.get_group(
            Matcher(all_of=[DeathComponent, MonsterComponent])
        ).entities
        for entity in entities:
            dead_caction = entity.get(DeathComponent)
            entity.replace(DestroyComponent, dead_caction.name)

    ########################################################################################################################################################################
    # 检查战斗结果的死亡情况
    def _check_combat_result(self) -> None:
        if not self._game.current_engagement.is_on_going_phase:
            # 不是本阶段就直接返回
            return

        if self._are_all_heroes_defeated():
            self._game.current_engagement.combat_complete(CombatResult.HERO_LOSE)
        elif self._are_all_monsters_defeated():
            self._game.current_engagement.combat_complete(CombatResult.HERO_WIN)
        else:
            logger.debug("combat continue!!!")

    ########################################################################################################################################################################
    def _are_all_monsters_defeated(self) -> bool:

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        actors_on_stage = self._game.retrieve_actors_on_stage(player_entity)
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

        actors_on_stage = self._game.retrieve_actors_on_stage(player_entity)
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
