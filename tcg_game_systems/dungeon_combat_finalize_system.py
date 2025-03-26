from loguru import logger
from entitas import Matcher, Entity, Matcher, ExecuteProcessor  # type: ignore
from components.components_v_0_0_1 import (
    SkillCandidateQueueComponent,
    CombatEffectsComponent,
    CombatAttributesComponent,
)
from overrides import override
from typing import List, Tuple, final
from game.tcg_game import TCGGame
from components.actions_v_0_0_1 import (
    TurnAction,
    StageDirectorAction,
    SelectAction,
    FeedbackAction,
)
from models.v_0_0_1 import Effect


#######################################################################################################################################
@final
class DungeonCombatFinalizeSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:
        if not self._game.combat_system.is_on_going_phase:
            return  # 不是本阶段就直接返回

        logger.info("DungeonCombatFinalizeSystem is executing...")
        logger.info(f"Current combat rounds: {len(self._game.combat_system.rounds)}")

        player_entity = self._game.get_player_entity()
        assert player_entity is not None

        stage_entity = self._game.safe_get_stage_entity(player_entity)
        assert stage_entity is not None

        skill_actors = self._game.get_group(
            Matcher(
                all_of=[
                    SkillCandidateQueueComponent,
                ],
            )
        ).entities

        # 出手的角色
        turn_actors = self._game.get_group(
            Matcher(
                all_of=[
                    TurnAction,
                ],
            )
        ).entities

        # 出手的角色
        selected_action_actors = self._game.get_group(
            Matcher(
                all_of=[
                    SelectAction,
                    FeedbackAction,
                ],
            )
        ).entities

        # 所有的角色，理论上都出手了。
        actors_on_stage = self._game.retrieve_actors_on_stage(stage_entity)
        assert len(turn_actors) == len(actors_on_stage)
        assert len(selected_action_actors) == len(actors_on_stage)

        assert len(turn_actors) > 0
        if len(turn_actors) == 0:
            logger.error(f"没有角色出手。???!!!!!")
            return

        if len(selected_action_actors) != len(turn_actors):
            logger.error(
                f"出手的角色数量和选择技能的角色数量不一致。可能是request有问题。"
            )
            return

        if not stage_entity.has(StageDirectorAction):
            logger.error(f"{stage_entity._name} 没有进行战斗演绎，应该是出错了。")
            return

        # 看一看出手顺序。
        first_turn_actor = next(iter(turn_actors))
        first_turn_action = first_turn_actor.get(TurnAction)
        logger.info(
            f"First turn actor: {first_turn_action.rounds}, {first_turn_action.round_turns}"
        )

    #######################################################################################################################################
    # 状态效果扣除。
    def _update_combat_remaining_effects(
        self, entity: Entity
    ) -> Tuple[List[Effect], List[Effect]]:

        # 效果更新
        assert entity.has(CombatEffectsComponent)
        combat_effects_comp = entity.get(CombatEffectsComponent)
        assert combat_effects_comp is not None

        current_effects = combat_effects_comp.effects.copy()
        remaining_effects = []
        removed_effects = []
        for i, e in enumerate(current_effects):
            current_effects[i].rounds -= 1
            current_effects[i].rounds = max(0, current_effects[i].rounds)

            if current_effects[i].rounds > 0:
                remaining_effects.append(current_effects[i])
            else:
                removed_effects.append(current_effects[i])

        entity.replace(
            CombatEffectsComponent, combat_effects_comp.name, remaining_effects
        )

        return remaining_effects, removed_effects

    ###############################################################################################################################################
    def _update_combat_health(self, entity: Entity, hp: float, max_hp: float) -> None:

        combat_attributes_comp = entity.get(CombatAttributesComponent)
        assert combat_attributes_comp is not None

        entity.replace(
            CombatAttributesComponent,
            combat_attributes_comp.name,
            hp,
            max_hp,
            combat_attributes_comp.physical_attack,
            combat_attributes_comp.physical_defense,
            combat_attributes_comp.magic_attack,
            combat_attributes_comp.magic_defense,
        )

    #######################################################################################################################################
