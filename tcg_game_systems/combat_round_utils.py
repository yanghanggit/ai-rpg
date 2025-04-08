from entitas import Entity  # type: ignore
from typing import List, Set, final, Tuple
from game.tcg_game import TCGGame
import random
from models_v_0_0_1 import BaseAttributesComponent, Round, StageEnvironmentComponent


@final
class CombatRoundUtils:

    ####################################################################################################################################
    def __init__(
        self,
        game_context: TCGGame,
        actor_entities: Set[Entity],
    ) -> None:

        self._game = game_context
        self._actor_entities = actor_entities
        assert len(actor_entities) > 0

    #######################################################################################################################################
    def initialize_round(self) -> Round:

        # 已经有一个回合，但是没有进行。
        if (
            len(self._game.current_engagement.rounds) > 0
            and not self._game.current_engagement.last_round.completed
        ):
            # 返回正在进行中的回合。
            return self._game.current_engagement.last_round

        # 开启一个新的回合。
        shuffled_reactive_entities = self._shuffle_action_order(
            list(self._actor_entities)
        )
        round_turns: List[str] = [entity._name for entity in shuffled_reactive_entities]
        self._game.current_engagement.new_round(round_turns)

        # 场景描写加上。
        first_entity = next(iter(self._actor_entities))
        stage_entity = self._game.safe_get_stage_entity(first_entity)
        assert stage_entity is not None
        stage_environment_comp = stage_entity.get(StageEnvironmentComponent)
        self._game.current_engagement.last_round.stage_environment = (
            stage_environment_comp.narrate
        )

        return self._game.current_engagement.last_round

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

            assert entity.has(BaseAttributesComponent)
            base_attributes_comp = entity.get(BaseAttributesComponent)
            actor_dexterity_pairs.append(
                (entity, base_attributes_comp.base_attributes.dexterity)
            )

        return [
            entity
            for entity, _ in sorted(
                actor_dexterity_pairs, key=lambda x: x[1], reverse=True
            )
        ]

    #######################################################################################################################################
