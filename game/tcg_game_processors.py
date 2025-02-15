from entitas import Processors  # type: ignore
from overrides import override
from typing import cast
from game.tcg_game_context import TCGGameContext
from game.base_game import BaseGame


class TCGGameProcessors(Processors):

    @staticmethod
    def create(game: BaseGame, context: TCGGameContext) -> "TCGGameProcessors":

        assert context is not None

        ### 不这样就循环引用
        from game.tcg_game import TCGGame

        ##
        tcg_game = cast(TCGGame, game)
        assert isinstance(tcg_game, TCGGame)
        processors = TCGGameProcessors()

        ## 添加一些系统。。。
        from tcg_game_systems.begin_system import BeginSystem
        from tcg_game_systems.end_system import EndSystem

        processors.add(BeginSystem(context))

        processors.add(EndSystem(context))

        return processors

    ###################################################################################################################################################################
    def __init__(self) -> None:
        super().__init__()
        self._initialized: bool = False

    ###################################################################################################################################################################
    @override
    def initialize(self) -> None:
        for processor in self._initialize_processors:
            processor.initialize()

    ###################################################################################################################################################################
    ## 异步执行方法
    async def a_execute(self) -> None:
        for processor in self._execute_processors:
            await processor.a_execute1()
            processor.execute()
            await processor.a_execute2()

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:
        for processor in self._execute_processors:
            processor.execute()

    ###################################################################################################################################################################
    @override
    def tear_down(self) -> None:
        for processor in self._tear_down_processors:
            processor.tear_down()


###################################################################################################################################################################
