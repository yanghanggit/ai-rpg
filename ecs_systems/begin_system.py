from typing import override
from entitas import InitializeProcessor, ExecuteProcessor #type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
   
class BeginSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context
############################################################################################################
    @override
    def initialize(self) -> None:
        pass
############################################################################################################
    @override
    def execute(self) -> None:
        self._context._execute_count += 1
        logger.debug(f"世界运行的回合数：{self._context._execute_count}")
############################################################################################################

