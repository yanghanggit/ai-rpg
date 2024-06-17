from typing import override
from entitas import (TearDownProcessor, ExecuteProcessor) #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger


class SaveSystem(ExecuteProcessor, TearDownProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__()
        self.context = context
        self.current_save_count = 0
################################################################################################
    @override
    def execute(self) -> None:
        ## 运行一定次数后自动保存
        if self.context.save_data_enable:
            self.auto_save_all(self.context.auto_save_trigger_count)
################################################################################################
    @override
    def tear_down(self) -> None:
        if self.context.save_data_enable:
            self.save_all()
################################################################################################
    def auto_save_all(self, auto_save_trigger_count: int) -> None:
        assert auto_save_trigger_count > 0
        self.current_save_count += 1
        if self.current_save_count >= auto_save_trigger_count:
            self.current_save_count = 0
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

