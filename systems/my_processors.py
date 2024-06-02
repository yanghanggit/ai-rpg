from typing import Coroutine
from entitas import Processors #type: ignore
from loguru import logger
from overrides import override
import time

class MyProcessors(Processors):

    def __init__(self) -> None:
        super().__init__()

    @override
    def initialize(self) -> None:
        for processor in self._initialize_processors:
            logger.debug(f"<<<<<<<<<<<<< initialize: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>")
            #processor.initialize()
            start_time = time.time()

            processor.initialize()
            
            end_time = time.time()
            execution_time = end_time - start_time
            logger.debug(f"{processor.__class__.__name__} initialize time: {execution_time:.2f} seconds")
            
    ## 异步执行方法
    async def async_execute(self) -> None:
        for processor in self._execute_processors:
            await processor.async_pre_execute()
            processor.execute()
            await processor.async_post_execute()
            
    @override
    def execute(self) -> None:
        for processor in self._execute_processors:
            logger.debug(f"<<<<<<<<<<<<< execute: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>")
            #processor.execute()
            start_time = time.time()
            
            processor.execute()
            
            end_time = time.time()
            execution_time = end_time - start_time
            logger.debug(f"{processor.__class__.__name__} execute time: {execution_time:.2f} seconds")

    @override
    def tear_down(self) -> None:
        for processor in self._tear_down_processors:
            logger.debug(f"<<<<<<<<<<<<< tear_down: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>")
            processor.tear_down()

   
