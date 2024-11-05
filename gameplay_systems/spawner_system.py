from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from my_components.components import (
    StageComponent,
    StageSpawnerComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from typing import final, Final, Optional
from rpg_game.rpg_game import RPGGame
from my_models.models_def import ActorInstanceModel, ActorModel
import copy


######################################################################################################################################################
@final
class SpawnerSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game
        self._base_index: Final[int] = 5 * 100 * 100
        self._gen_index: int = 0

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        self.test_execute()

    ######################################################################################################################################################
    def test_execute(self) -> None:
        stage_entities = self._context.get_group(
            Matcher(all_of=[StageComponent, StageSpawnerComponent])
        ).entities

        for stage_entity in stage_entities:

            stage_spawner_component = stage_entity.get(StageSpawnerComponent)
            for spawner_name in stage_spawner_component.spawners:
                self._spawn(spawner_name)

    ######################################################################################################################################################
    def _spawn(self, spawner_name: str) -> None:
        assert self._game._game_resource is not None
        assert self._game._game_resource.data_base is not None

        spawner_data = self._game._game_resource.data_base.get_spawner(spawner_name)
        if spawner_data is None:
            return

        for actor_prototype in spawner_data.actor_prototype:
            actor_model = self._game._game_resource.data_base.get_actor(
                actor_prototype.name
            )
            if actor_model is None:
                assert False, f"actor_prototype.name: {actor_prototype.name} not found"
                continue

            actor_prototype_copy = copy.deepcopy(actor_prototype)
            gen_guid = self._gen_actor_guid()
            hack_name = f"""{actor_prototype.name}#{gen_guid}"""
            actor_prototype_copy.name = hack_name
            actor_prototype_copy.guid = gen_guid
            self._spawn_actor_entity(actor_prototype_copy, actor_model)

    ######################################################################################################################################################
    def _spawn_actor_entity(
        self, actor_instance: ActorInstanceModel, actor_model: ActorModel
    ) -> Optional[Entity]:

        logger.debug(f"actor_instance: {actor_instance}")
        logger.debug(f"actor_model: {actor_model}")
        return None

    ######################################################################################################################################################
    def _gen_actor_guid(
        self,
    ) -> int:

        self._gen_index += 1
        return self._base_index + self._gen_index

    ######################################################################################################################################################
