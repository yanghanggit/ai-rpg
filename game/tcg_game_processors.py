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
        from tcg_game_systems.kick_off_system import KickOffSystem
        from tcg_game_systems.save_system import SaveSystem
        from tcg_game_systems.handle_terminal_player_input_system import (
            HandleTerminalPlayerInputSystem,
        )
        from tcg_game_systems.handle_web_player_input_system import (
            HandleWebPlayerInputSystem,
        )
        from tcg_game_systems.terminal_player_interrupt_wait_system import (
            TerminalPlayerInterruptWaitSystem,
        )
        from tcg_game_systems.mind_voice_action_system import (
            MindVoiceActionSystem,
        )
        from tcg_game_systems.whisper_action_system import WhisperActionSystem

        from tcg_game_systems.speak_action_system import SpeakActionSystem
        from tcg_game_systems.announce_action_system import AnnounceActionSystem
        from tcg_game_systems.pre_action_system import PreActionSystem
        from tcg_game_systems.post_action_system import PostActionSystem
        from tcg_game_systems.destroy_system import DestroySystem
        from tcg_game_systems.dead_action_system import DeadActionSystem
        from tcg_game_systems.pre_planning_system import PrePlanningSystem
        from tcg_game_systems.post_planning_system import PostPlanningSystem
        from tcg_game_systems.stage_planning_system import StagePlanningSystem
        from tcg_game_systems.actor_planning_system import ActorPlanningSystem
        from tcg_game_systems.world_system_planning_system import (
            WorldSystemPlanningSystem,
        )
        from tcg_game_systems.tag_action_system import TagActionSystem
        from tcg_game_systems.go_to_action_system import GoToActionSystem

        processors.add(BeginSystem(context))

        # 启动agent的提示词。启动阶段
        processors.add(KickOffSystem(context))

        # 进入动作前，处理输入。
        processors.add(HandleTerminalPlayerInputSystem(context))
        processors.add(HandleWebPlayerInputSystem(context))

        # 动作处理相关的系统
        processors.add(PreActionSystem(context))

        # processors.add(TagActionSystem(context))
        processors.add(MindVoiceActionSystem(context))
        processors.add(WhisperActionSystem(context))
        processors.add(AnnounceActionSystem(context))
        processors.add(SpeakActionSystem(context))

        # ?
        processors.add(DeadActionSystem(context))

        # 战斗之后，执行场景更换的逻辑，如果上面死亡了，就不能执行下面的！
        # processors.add(GoToActionSystem(context))

        # ?
        processors.add(PostActionSystem(context))

        # 动作处理后，可能清理。
        processors.add(DestroySystem(context))

        #
        processors.add(TerminalPlayerInterruptWaitSystem(context))

        # 规划逻辑
        processors.add(PrePlanningSystem(context))  ######## 在所有规划之前!

        processors.add(WorldSystemPlanningSystem(context))
        processors.add(StagePlanningSystem(context))
        processors.add(ActorPlanningSystem(context))

        processors.add(PostPlanningSystem(context))  ####### 在所有规划之后!

        # 存储系统。
        processors.add(SaveSystem(context))

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
