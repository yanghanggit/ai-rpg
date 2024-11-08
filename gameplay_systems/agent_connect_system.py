from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override
from my_components.components import (
    WorldComponent,
    StageComponent,
    ActorComponent,
    AgentConnectionFlagComponent,
)
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from loguru import logger


@final
class AgentConnectSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ###############################################################################################################################################
    @override
    def execute(self) -> None:
        self._connect_all_agents()

    ###############################################################################################################################################
    def _connect_all_agents(self) -> None:

        unconnected_entities = self._context.get_group(
            Matcher(
                any_of=[WorldComponent, StageComponent, ActorComponent],
                none_of=[AgentConnectionFlagComponent],
            )
        ).entities.copy()

        for entity in unconnected_entities:

            safe_name = self._context.safe_get_entity_name(entity)
            if safe_name == "":
                continue

            agent = self._context._langserve_agent_system.get_agent(safe_name)
            if agent is None:
                continue

            if agent.remote_runnable is not None:
                continue

            if self._context._langserve_agent_system.connect_agent(safe_name):
                entity.replace(AgentConnectionFlagComponent, safe_name)


###############################################################################################################################################
