from entitas import Entity, Matcher, ExecuteProcessor  # type: ignore
from overrides import override
from components.components import (
    StageComponent,
    StageSpawnerComponent,
)
from game.rpg_game_context import RPGGameContext
from typing import final, List
from game.rpg_game import RPGGame
import copy
from format_string.complex_actor_name import ComplexActorName
from rpg_models.editor_models import GUIDType


######################################################################################################################################################
@final
class StageSpawnerSystem(ExecuteProcessor):
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game
        self._gen_index: int = 0

    ######################################################################################################################################################
    @override
    def execute(self) -> None:
        self._test()

    ######################################################################################################################################################
    def _test(self) -> None:
        stage_entities = self._context.get_group(
            Matcher(all_of=[StageComponent, StageSpawnerComponent])
        ).entities

        for stage_entity in stage_entities:
            stage_spawner_component = stage_entity.get(StageSpawnerComponent)
            for spawner_name in stage_spawner_component.spawners:
                self._execute_spawn(spawner_name, stage_entity)

    ######################################################################################################################################################
    def _execute_spawn(self, spawner_name: str, stage_entity: Entity) -> List[Entity]:
        assert self._game._game_resource is not None
        assert self._game._game_resource.data_base is not None

        spawner_data = self._game._game_resource.data_base.get_spawner(spawner_name)
        if spawner_data is None:
            return []

        ret: List[Entity] = []

        for actor_instance_as_prototype_name in spawner_data.actor_prototypes:

            actor_intance_as_prototype = self._game._game_resource.get_actor_instance(
                actor_instance_as_prototype_name
            )
            if actor_intance_as_prototype is None:
                assert (
                    False
                ), f"actor_prototype.name: {actor_instance_as_prototype_name} not found"
                continue

            actor_model = self._game._game_resource.data_base.get_actor(
                ComplexActorName.extract_name(actor_instance_as_prototype_name)
            )
            if actor_model is None:
                assert (
                    False
                ), f"actor_prototype.name: {actor_instance_as_prototype_name} not found"
                continue

            # 必须深拷贝，否则会出问题
            actor_intance_deep_copy = copy.deepcopy(actor_intance_as_prototype)
            # 生成一个guid
            gen_new_guid = self._gen_actor_guid()
            # 生成一个新的 + guid
            actor_intance_deep_copy.name = ComplexActorName.format_name_with_guid(
                ComplexActorName.extract_name(actor_instance_as_prototype_name),
                gen_new_guid,
            )
            actor_intance_deep_copy.guid = gen_new_guid
            # 生成一个新的entity
            spawned_actor_entity = self._game.create_actor_entity_at_runtime(
                actor_intance_deep_copy, actor_model, stage_entity
            )
            if spawned_actor_entity is not None:
                ret.append(spawned_actor_entity)

        return ret

    ######################################################################################################################################################
    def _gen_actor_guid(self) -> int:
        self._gen_index += 1
        return GUIDType.RUNTIME_ACTOR_TYPE + self._gen_index

    ######################################################################################################################################################
