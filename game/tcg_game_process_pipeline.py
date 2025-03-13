from entitas import Processors  # type: ignore
from overrides import override
from typing import cast
from game.base_game import BaseGame


class TCGGameProcessPipeline(Processors):
    """
    熟悉项目用的，后续会做改良在HOME时候使用
    """

    @staticmethod
    def create_home_state_pipline(game: BaseGame) -> "TCGGameProcessPipeline":

        ### 不这样就循环引用
        from game.tcg_game import TCGGame

        ##
        tcg_game = cast(TCGGame, game)
        assert isinstance(tcg_game, TCGGame)
        processors = TCGGameProcessPipeline()

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

        # from tcg_game_systems.terminal_player_interrupt_wait_system import (
        #     TerminalPlayerInterruptWaitSystem,
        # )
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
        from tcg_game_systems.stage_narrate_planning_system import (
            StageNarratePlanningSystem,
        )
        from tcg_game_systems.actor_roleplay_planning_system import (
            ActorRoleplayPlanningSystem,
        )

        from tcg_game_systems.actor_roleplay_planning_permit_system import (
            ActorRoleplayPlanningPermitSystem,
        )
        from tcg_game_systems.stage_narrate_planning_permit_system import (
            StageNarratePlanningPermitSystem,
        )

        # 进入动作前，处理输入。
        processors.add(HandleTerminalPlayerInputSystem(tcg_game))
        processors.add(HandleWebPlayerInputSystem(tcg_game))

        processors.add(BeginSystem(tcg_game))

        # 启动agent的提示词。启动阶段
        processors.add(KickOffSystem(tcg_game))

        # 动作处理相关的系统
        processors.add(PreActionSystem(tcg_game))

        # 说话相关动作。
        processors.add(MindVoiceActionSystem(tcg_game))
        processors.add(WhisperActionSystem(tcg_game))
        processors.add(AnnounceActionSystem(tcg_game))
        processors.add(SpeakActionSystem(tcg_game))

        # ?
        processors.add(DeadActionSystem(tcg_game))

        # ?
        processors.add(PostActionSystem(tcg_game))

        # 动作处理后，可能清理。
        processors.add(DestroySystem(tcg_game))

        # debug 用，看需求
        # processors.add(TerminalPlayerInterruptWaitSystem(context))

        # 规划逻辑
        processors.add(PrePlanningSystem(tcg_game))  ######## 在所有规划之前!

        processors.add(StageNarratePlanningPermitSystem(tcg_game))
        processors.add(ActorRoleplayPlanningPermitSystem(tcg_game))

        processors.add(StageNarratePlanningSystem(tcg_game))
        processors.add(ActorRoleplayPlanningSystem(tcg_game))

        processors.add(PostPlanningSystem(tcg_game))  ####### 在所有规划之后!

        # 存储系统。
        processors.add(SaveSystem(tcg_game))

        processors.add(EndSystem(tcg_game))

        return processors

    ###################################################################################################################################################################

    """
    临时先这么写！！！！！！！！！1
    """

    @staticmethod
    def create_dungeon_state_pipeline(game: BaseGame) -> "TCGGameProcessPipeline":

        ### 不这样就循环引用
        from game.tcg_game import TCGGame

        #
        ##
        tcg_game = cast(TCGGame, game)
        assert isinstance(tcg_game, TCGGame)
        processors = TCGGameProcessPipeline()

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
        from tcg_game_systems.destroy_system import DestroySystem

        from tcg_game_systems.B1_TurnStartSystem import B1_TurnStartSystem
        from tcg_game_systems.B2_ActorPlanSystem import B2_ActorPlanSystem
        from tcg_game_systems.B5_ExecuteHitsSystem import B5_ExecuteHitsSystem
        from tcg_game_systems.B6_CheckEndSystem import B6_CheckEndSystem

        from tcg_game_systems.pre_dungeon_state_system import PreDungeonStateSystem
        from tcg_game_systems.post_dungeon_state_system import PostDungeonStateSystem
        from tcg_game_systems.status_update_action_system import (
            StatusUpdateActionSystem,
        )

        # 用户输入转入pipeline 执行序列
        processors.add(HandleTerminalPlayerInputSystem(tcg_game))
        processors.add(HandleWebPlayerInputSystem(tcg_game))

        # 标记开始。
        processors.add(BeginSystem(tcg_game))

        # 启动agent的提示词。启动阶段
        processors.add(KickOffSystem(tcg_game))

        # yh add, 测试用。
        processors.add(PreDungeonStateSystem(tcg_game))

        # yh add, 测试用。
        processors.add(StatusUpdateActionSystem(tcg_game))

        # 战斗逻辑。
        processors.add(B1_TurnStartSystem(tcg_game))
        processors.add(B2_ActorPlanSystem(tcg_game))
        processors.add(B5_ExecuteHitsSystem(tcg_game))
        processors.add(B6_CheckEndSystem(tcg_game))

        # yh add, 测试用。
        processors.add(PostDungeonStateSystem(tcg_game))

        # 动作处理后，可能删除掉一些entities。
        processors.add(DestroySystem(tcg_game))

        # 存储系统。
        processors.add(SaveSystem(tcg_game))

        # 结束
        processors.add(EndSystem(tcg_game))

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
