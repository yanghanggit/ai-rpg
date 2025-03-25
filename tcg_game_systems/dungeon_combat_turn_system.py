import random
from entitas import Matcher, Entity, Matcher, ExecuteProcessor  # type: ignore
from components.components_v_0_0_1 import (
    SkillCandidateQueueComponent,
)
from overrides import override
from typing import List, Tuple, final
from game.tcg_game import TCGGame
from components.actions import SelectAction, TurnAction


#######################################################################################################################################
@final
class DungeonCombatTurnSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    def execute(self) -> None:

        if not self._game.combat_system.latest_combat.is_on_going:
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
        # shuffled_reactive_entities = self._sort_action_order_by_dex(
        #     shuffled_reactive_entities
        # )
        new_round.turns = [entity._name for entity in shuffled_reactive_entities]

        # 测试的代码 TODO
        for turn_index, name in enumerate(new_round.turns):
            entity2 = self._game.get_entity_by_name(name)
            assert entity2 is not None
            assert not entity2.has(TurnAction)
            assert not entity2.has(SelectAction)
            entity2.replace(TurnAction, entity2._name)
            entity2.replace(SelectAction, entity2._name)

    #######################################################################################################################################
    # 随机排序
    def _shuffle_action_order(self, react_entities: List[Entity]) -> List[Entity]:
        shuffled_reactive_entities = react_entities.copy()
        random.shuffle(shuffled_reactive_entities)
        return shuffled_reactive_entities

    #######################################################################################################################################
    # 正式的排序方式，按着敏捷度排序
    def _sort_action_order_by_dex(self, react_entities: List[Entity]) -> List[Entity]:

        actor_dexterity_pairs: List[Tuple[Entity, int]] = []
        for entity in react_entities:
            actor_instance = self._game.retrieve_actor_instance(entity)
            assert actor_instance is not None
            actor_dexterity_pairs.append(
                (entity, actor_instance.base_attributes.dexterity)
            )

        return [
            entity
            for entity, _ in sorted(
                actor_dexterity_pairs, key=lambda x: x[1], reverse=True
            )
        ]

    #######################################################################################################################################
