from typing import Set
from overrides import override
from loguru import logger
from game.tcg_game_context import TCGGameContext
from game.base_game import BaseGame
from game.tcg_game_processors import TCGGameProcessors
from models.event_models import BaseEvent
from models.entity_models import WorldRuntime, WorldRoot


class TCGGame(BaseGame):

    def __init__(
        self, name: str, world_runtime: WorldRuntime, context: TCGGameContext
    ) -> None:

        # 必须实现父
        super().__init__(name)

        self._context: TCGGameContext = context
        self._context._game = self
        self._world_runtime: WorldRuntime = world_runtime
        self._processors: TCGGameProcessors = TCGGameProcessors.create(self, context)

    ###############################################################################################################################################
    @property
    def context(self) -> TCGGameContext:
        return self._context

    ###############################################################################################################################################
    @override
    def execute(self) -> None:
        # 顺序不要动
        current_processors = self._processors
        if not current_processors._initialized:
            current_processors._initialized = True
            current_processors.activate_reactive_processors()
            current_processors.initialize()

        current_processors.execute()
        current_processors.cleanup()

    ###############################################################################################################################################
    @override
    async def a_execute(self) -> None:
        # 顺序不要动
        current_processors = self._processors
        if not current_processors._initialized:
            current_processors._initialized = True
            current_processors.activate_reactive_processors()
            current_processors.initialize()

        await current_processors.a_execute()
        current_processors.cleanup()

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        all = [self._processors]
        for processor in all:
            processor.tear_down()
            processor.clear_reactive_processors()

        logger.info(f"{self._name}, game over!!!!!!!!!!!!!!!!!!!!")

    ###############################################################################################################################################
    @override
    def send_event(self, player_proxy_names: Set[str], send_event: BaseEvent) -> None:
        pass

    ###############################################################################################################################################
