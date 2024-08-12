from typing import override
from entitas import (TearDownProcessor, ExecuteProcessor) #type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame 


class SaveSystem(ExecuteProcessor, TearDownProcessor):

    def __init__(self, context: RPGEntitasContext, rpggame: RPGGame) -> None:
        super().__init__()
        self._context = context
        self._rpggame = rpggame
################################################################################################
    @override
    def execute(self) -> None:
        self.save_all()
################################################################################################
    @override
    def tear_down(self) -> None:
        self.save_all()
################################################################################################
    def save_all(self) -> None:
        self.save_world()
        self.save_stage()
        self.save_actor()
################################################################################################
    def save_world(self) -> None:
        #todo
        logger.warning("save_world")
################################################################################################
    def save_stage(self) -> None:
        #todo
        logger.warning("save_stage")
################################################################################################
    def save_actor(self) -> None:
        #todo
        logger.warning("save_actor")
################################################################################################