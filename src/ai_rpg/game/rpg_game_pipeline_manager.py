"""
RPG游戏流程管道管理器模块

本模块定义了RPG游戏流程管道的管理器类，负责管理和协调所有游戏流程管道的生命周期。
"""

from typing import Final, List
from ..entitas import Processors


###################################################################################################################################################################
class RPGGameProcessPipeline(Processors):
    """
    RPG游戏流程管道

    管理游戏流程中的处理器执行和生命周期
    """

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name: Final[str] = name

    ###################################################################################################################################################################
    async def process(self) -> None:
        """执行管道中的所有处理器"""
        # 顺序不要动
        # logger.debug(
        #     f"================= {self._name} process pipeline process ================="
        # )
        await self.execute()
        self.cleanup()

    ###############################################################################################################################################
    def shutdown(self) -> None:
        """关闭管道并清理资源"""
        # logger.debug(
        #     f"================= {self._name} process pipeline shutdown ================="
        # )
        self.tear_down()
        self.clear_reactive_processors()


################################################################################################################################################
class RPGGamePipelineManager:
    """
    RPG游戏流程管道管理器

    负责管理和协调所有游戏流程管道的生命周期
    """

    def __init__(self) -> None:
        self._all_pipelines: List[RPGGameProcessPipeline] = []

    ###############################################################################################################################################
    def register_pipeline(self, pipeline: RPGGameProcessPipeline) -> None:
        """注册一个游戏流程管道"""
        self._all_pipelines.append(pipeline)

    ###############################################################################################################################################
    async def initialize_all_pipelines(self) -> None:
        """初始化所有已注册的管道"""
        for processor in self._all_pipelines:
            processor.activate_reactive_processors()
            await processor.initialize()

    ###############################################################################################################################################
    def shutdown_all_pipelines(self) -> None:
        """关闭所有管道并清空管道列表"""
        for processor in self._all_pipelines:
            processor.shutdown()
        self._all_pipelines.clear()
