from entitas import ExecuteProcessor, Matcher  # type: ignore
from game.rpg_game_context import RPGGameContext
from components.components import (
    StageComponent,
    ActorComponent,
)
from typing import final, override, NamedTuple, FrozenSet
import rpg_game_systems.file_system_utils
from game.rpg_game import RPGGame
from rpg_models.file_models import ComponentDumpModel, EntityProfileModel
from collections import OrderedDict


@final
class SaveEntitySystem(ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._save()

    ############################################################################################################
    def _save(self) -> None:

        #
        entity_dumps = self._get_entity_profiles(
            frozenset({StageComponent, ActorComponent})
        )
        for key, value in entity_dumps.items():
            rpg_game_systems.file_system_utils.persist_entity_profile(
                self._context.file_system, value
            )

    ############################################################################################################
    def _get_entity_profiles(
        self, component_types: FrozenSet[type[NamedTuple]]
    ) -> OrderedDict[str, EntityProfileModel]:

        ret: OrderedDict[str, EntityProfileModel] = OrderedDict()

        entities = self._context.get_group(Matcher(any_of=component_types)).entities

        for entity in entities:

            safe_name = self._context.safe_get_entity_name(entity)
            if safe_name == "":
                continue

            entity_dump = EntityProfileModel(name=safe_name, components=[])
            for key, value in entity._components.items():
                entity_dump.components.append(
                    ComponentDumpModel(name=key.__name__, data=value._asdict())
                )

            ret[safe_name] = entity_dump

        return ret


############################################################################################################
