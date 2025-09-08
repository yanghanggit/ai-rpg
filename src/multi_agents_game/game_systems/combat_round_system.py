from typing import final, override
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame


@final
class CombatRoundSystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    #######################################################################################################################################
    @override
    async def execute(self) -> None:
        self._game.setup_round()
        # if not self._game.current_engagement.is_on_going_phase:
        #     return

        # self._setup_round()

    #######################################################################################################################################
    # def _setup_round(self) -> bool:

    #     if not self._game.current_engagement.is_on_going_phase:
    #         return False

    #     if (
    #         len(self._game.current_engagement.rounds) > 0
    #         and not self._game.current_engagement.last_round.has_ended
    #     ):
    #         # 返回正在进行中的回合。
    #         return False

    #     # 排序角色
    #     player_entity = self._game.get_player_entity()
    #     assert player_entity is not None
    #     actors_on_stage = self._game.retrieve_actors_on_stage(player_entity)
    #     assert len(actors_on_stage) > 0
    #     shuffled_reactive_entities = self._shuffle_action_order(list(actors_on_stage))

    #     # 场景描写加上。
    #     first_entity = next(iter(shuffled_reactive_entities))
    #     stage_entity = self._game.safe_get_stage_entity(first_entity)
    #     assert stage_entity is not None
    #     stage_environment_comp = stage_entity.get(EnvironmentComponent)

    #     round = self._game.current_engagement.new_round(
    #         round_turns=[entity._name for entity in shuffled_reactive_entities]
    #     )

    #     round.stage_environment = stage_environment_comp.narrate
    #     logger.info(f"CombatRoundSystem: _setup_round: {round.model_dump_json()}")
    #     return True

    # #######################################################################################################################################
    # # 随机排序
    # def _shuffle_action_order(self, actor_entities: List[Entity]) -> List[Entity]:
    #     shuffled_reactive_entities = actor_entities.copy()
    #     random.shuffle(shuffled_reactive_entities)
    #     return shuffled_reactive_entities

    # #######################################################################################################################################
    # # 正式的排序方式，按着敏捷度排序
    # def _sort_action_order_by_dex(self, actor_entities: List[Entity]) -> List[Entity]:

    #     actor_dexterity_pairs: List[Tuple[Entity, int]] = []
    #     for entity in actor_entities:

    #         assert entity.has(RPGCharacterProfileComponent)
    #         rpg_character_profile_component = entity.get(RPGCharacterProfileComponent)
    #         actor_dexterity_pairs.append(
    #             (
    #                 entity,
    #                 rpg_character_profile_component.rpg_character_profile.dexterity,
    #             )
    #         )

    #     return [
    #         entity
    #         for entity, _ in sorted(
    #             actor_dexterity_pairs, key=lambda x: x[1], reverse=True
    #         )
    #     ]

    #######################################################################################################################################
