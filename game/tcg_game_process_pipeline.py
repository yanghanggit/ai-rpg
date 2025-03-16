from entitas import Processors  # type: ignore
from overrides import override
from typing import cast
from game.base_game import BaseGame


class TCGGameProcessPipeline(Processors):

    @staticmethod
    def create_home_state_pipline(game: BaseGame) -> "TCGGameProcessPipeline":

        ### 不这样就循环引用
        from game.tcg_game import TCGGame

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
        from tcg_game_systems.mind_voice_action_system import (
            MindVoiceActionSystem,
        )
        from tcg_game_systems.speak_action_system import SpeakActionSystem
        from tcg_game_systems.pre_action_system import PreActionSystem
        from tcg_game_systems.post_action_system import PostActionSystem
        from tcg_game_systems.destroy_system import DestroySystem
        from tcg_game_systems.dead_action_system import DeadActionSystem
        from tcg_game_systems.pre_planning_system import PrePlanningSystem
        from tcg_game_systems.post_planning_system import PostPlanningSystem

        from tcg_game_systems.stage_planning_system import (
            StagePlanningSystem,
        )
        from tcg_game_systems.actor_planning_system import (
            ActorPlanningSystem,
        )

        from tcg_game_systems.actor_planning_permit_system import (
            ActorPlanningPermitSystem,
        )

        from tcg_game_systems.stage_planning_permit_system import (
            StagePlanningPermitSystem,
        )

        # from tcg_game_systems.pre_dungeon_state_system import PreDungeonStateSystem
        # from tcg_game_systems.post_dungeon_state_system import PostDungeonStateSystem

        ##
        tcg_game = cast(TCGGame, game)
        assert isinstance(tcg_game, TCGGame)
        processors = TCGGameProcessPipeline()

        # 进入动作前，处理输入。
        processors.add(HandleTerminalPlayerInputSystem(tcg_game))
        processors.add(HandleWebPlayerInputSystem(tcg_game))

        processors.add(BeginSystem(tcg_game))

        # 启动agent的提示词。启动阶段
        processors.add(KickOffSystem(tcg_game))

        # 规划逻辑
        processors.add(PrePlanningSystem(tcg_game))  ######## 在所有规划之前!

        processors.add(StagePlanningPermitSystem(tcg_game))
        processors.add(ActorPlanningPermitSystem(tcg_game))

        processors.add(StagePlanningSystem(tcg_game))
        processors.add(ActorPlanningSystem(tcg_game))

        processors.add(PostPlanningSystem(tcg_game))  ####### 在所有规划之后!

        # 动作处理相关的系统
        processors.add(PreActionSystem(tcg_game))

        # 说话相关动作。
        processors.add(MindVoiceActionSystem(tcg_game))
        processors.add(SpeakActionSystem(tcg_game))

        # ?
        processors.add(DeadActionSystem(tcg_game))

        # ?
        processors.add(PostActionSystem(tcg_game))

        # 动作处理后，可能清理。
        processors.add(DestroySystem(tcg_game))

        # 存储系统。
        processors.add(SaveSystem(tcg_game))

        processors.add(EndSystem(tcg_game))

        return processors

    ###################################################################################################################################################################

    @staticmethod
    def create_dungeon_state_pipeline(game: BaseGame) -> "TCGGameProcessPipeline":

        ### 不这样就循环引用
        from game.tcg_game import TCGGame

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
        from tcg_game_systems.mind_voice_action_system import (
            MindVoiceActionSystem,
        )
        from tcg_game_systems.speak_action_system import SpeakActionSystem
        from tcg_game_systems.pre_action_system import PreActionSystem
        from tcg_game_systems.post_action_system import PostActionSystem
        from tcg_game_systems.destroy_system import DestroySystem
        from tcg_game_systems.dead_action_system import DeadActionSystem
        from tcg_game_systems.pre_planning_system import PrePlanningSystem
        from tcg_game_systems.post_planning_system import PostPlanningSystem

        from tcg_game_systems.stage_planning_system import (
            StagePlanningSystem,
        )
        from tcg_game_systems.actor_planning_system import (
            ActorPlanningSystem,
        )

        from tcg_game_systems.actor_planning_permit_system import (
            ActorPlanningPermitSystem,
        )

        from tcg_game_systems.stage_planning_permit_system import (
            StagePlanningPermitSystem,
        )
        from tcg_game_systems.pre_dungeon_state_system import PreDungeonStateSystem
        from tcg_game_systems.post_dungeon_state_system import PostDungeonStateSystem
        from tcg_game_systems.candidate_action_system import (
            CandidateActionSystem,
        )
        from tcg_game_systems.select_action_system import SelectActionSystem
        from tcg_game_systems.hit_action_system import HitActionSystem
        from tcg_game_systems.feedback_action_system import FeedbackActionSystem

        #
        ##
        tcg_game = cast(TCGGame, game)
        assert isinstance(tcg_game, TCGGame)
        processors = TCGGameProcessPipeline()

        # 用户输入转入pipeline 执行序列
        processors.add(HandleTerminalPlayerInputSystem(tcg_game))
        processors.add(HandleWebPlayerInputSystem(tcg_game))

        # 标记开始。
        processors.add(BeginSystem(tcg_game))

        # 启动agent的提示词。启动阶段
        processors.add(KickOffSystem(tcg_game))

        # yh add, 测试用。
        processors.add(PreDungeonStateSystem(tcg_game))

        # 规划逻辑
        processors.add(PrePlanningSystem(tcg_game))  ######## 在所有规划之前!

        processors.add(StagePlanningPermitSystem(tcg_game))
        processors.add(ActorPlanningPermitSystem(tcg_game))

        processors.add(StagePlanningSystem(tcg_game))

        processors.add(PostPlanningSystem(tcg_game))  ####### 在所有规划之后!

        # yh add, 测试用。
        processors.add(PreActionSystem(tcg_game))

        # yh test
        processors.add(
            CandidateActionSystem(tcg_game)
        )  ##################################
        processors.add(SelectActionSystem(tcg_game))
        processors.add(HitActionSystem(tcg_game))
        processors.add(FeedbackActionSystem(tcg_game))
        processors.add(DeadActionSystem(tcg_game))  ##################################

        processors.add(PostActionSystem(tcg_game))

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
