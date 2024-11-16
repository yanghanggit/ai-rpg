import asyncio
import time
from entitas import Matcher, Entity, ExecuteProcessor  # type: ignore
from typing import Any, Coroutine, Set, final, override, List
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
        pass

    ###############################################################################################################################################
    @override
    async def a_execute1(self) -> None:

        # 准备所有未连接的实体
        unconnected_entities = self._context.get_group(
            Matcher(
                any_of=[WorldComponent, StageComponent, ActorComponent],
                none_of=[AgentConnectionFlagComponent],
            )
        ).entities.copy()

        # 创建任务来并发连接所有未连接的实体
        connect_task = self._initialize_agent_connections(unconnected_entities)
        start_time = time.time()
        await asyncio.gather(*connect_task)
        end_time = time.time()
        logger.debug(f"AgentConnectSystem.gather:{end_time - start_time:.2f} seconds")

        # 连接完成后，更新所有已连接的实体
        self._process_agent_connections(unconnected_entities)

    ###############################################################################################################################################
    def _initialize_agent_connections(
        self, unconnected_entities: Set[Entity]
    ) -> List[Coroutine[Any, Any, Any]]:

        ret: List[Coroutine[Any, Any, Any]] = []

        for entity in unconnected_entities:
            agent = self._context.safe_get_agent(entity)
            if agent.remote_runnable is None:
                ret.append(agent.remote_connector.initialize_connection("你是谁?"))

        return ret

    ###############################################################################################################################################
    def _process_agent_connections(self, unconnected_entities: Set[Entity]) -> None:
        for entity in unconnected_entities:
            agent = self._context.safe_get_agent(entity)
            if agent.remote_runnable is not None:
                entity.replace(AgentConnectionFlagComponent, agent.name)
                logger.debug(
                    f"AgentConnectSystem._process_agent_connections:{agent.name} connected"
                )

    ###############################################################################################################################################
