import random
from entitas import Matcher, Entity, Matcher, ExecuteProcessor  # type: ignore
from components.components import (
    SkillCandidateQueueComponent,
)
from overrides import override
from typing import List, final
from game.tcg_game import TCGGame
from extended_systems.combat_system import CombatState
from components.actions2 import SelectAction2, TurnAction2


#######################################################################################################################################
@final
class DungeonCombatTurnSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:

        if self._game.combat_system.latest_combat.current_state != CombatState.RUNNING:
            # 不是本阶段就直接返回
            return

        actor_entities = self._game.get_group(
            Matcher(
                all_of=[
                    SkillCandidateQueueComponent,
                ],
            )
        ).entities

        if len(actor_entities) == 0:
            return

        new_round = self._game.combat_system.latest_combat.start_new_round()

        # 随机出手顺序
        shuffled_reactive_entities = self._shuffle_action_order(list(actor_entities))
        new_round.turns = [entity._name for entity in shuffled_reactive_entities]

        # 测试的代码 TODO
        for turn_index, name in enumerate(new_round.turns):
            entity2 = self._game.get_entity_by_name(name)
            assert entity2 is not None
            assert not entity2.has(TurnAction2)
            assert not entity2.has(SelectAction2)
            entity2.replace(TurnAction2, entity2._name)
            entity2.replace(SelectAction2, entity2._name)

    #######################################################################################################################################
    def _shuffle_action_order(self, react_entities: List[Entity]) -> List[Entity]:
        shuffled_reactive_entities = react_entities.copy()
        random.shuffle(shuffled_reactive_entities)
        return shuffled_reactive_entities

    #######################################################################################################################################
