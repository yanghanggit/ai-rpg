from loguru import logger
from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override
from components.components_v_0_0_1 import DestroyComponent, DeathComponent
from models.v_0_0_1 import CombatResult
from game.tcg_game import TCGGame
from components.components_v_0_0_1 import (
    CombatRoleComponent,
    HeroComponent,
    MonsterComponent,
)


@final
class DeathSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ########################################################################################################################################################################
    @override
    def execute(self) -> None:

        # 处理血量为0的情况
        self._update_entities_to_dead_state()

        # 添加销毁
        self._add_destroyed_monster_entities()

        # 检查战斗结果的死亡情况
        self._check_combat_result()

    ########################################################################################################################################################################
    def _update_entities_to_dead_state(self) -> None:
        entities = self._game.get_group(
            Matcher(all_of=[CombatRoleComponent], none_of=[DeathComponent])
        ).entities.copy()
        for entity in entities:
            combat_role_comp = entity.get(CombatRoleComponent)
            if combat_role_comp.hp <= 0:
                logger.debug(f"{combat_role_comp.name} is dead")
                self._game.append_human_message(entity, "# 你已被击败！")
                entity.replace(DeathComponent, combat_role_comp.name)

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
        if not self._game.current_engagement_system.is_on_going_phase:
            # 不是本阶段就直接返回
            return

        if self._are_all_heroes_defeated():
            self._game.current_engagement_system.combat_complete(CombatResult.HERO_LOSE)
        elif self._are_all_monsters_defeated():
            self._game.current_engagement_system.combat_complete(CombatResult.HERO_WIN)
        else:
            logger.debug("combat continue!!!")

    ########################################################################################################################################################################
    def _are_all_heroes_defeated(self) -> bool:
        entities1 = self._game.get_group(
            Matcher(all_of=[HeroComponent, DeathComponent, CombatRoleComponent])
        ).entities

        entities2 = self._game.get_group(
            Matcher(all_of=[HeroComponent, CombatRoleComponent])
        ).entities

        assert len(entities2) > 0, f"entities with actions: {entities2}"
        return len(entities2) > 0 and len(entities1) >= len(entities2)

    ########################################################################################################################################################################
    def _are_all_monsters_defeated(self) -> bool:
        entities1 = self._game.get_group(
            Matcher(all_of=[MonsterComponent, DeathComponent, CombatRoleComponent])
        ).entities

        entities2 = self._game.get_group(
            Matcher(all_of=[MonsterComponent, CombatRoleComponent])
        ).entities

        assert len(entities2) > 0, f"entities with actions: {entities2}"
        return len(entities2) > 0 and len(entities1) >= len(entities2)


########################################################################################################################################################################
