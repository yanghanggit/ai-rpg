from loguru import logger
from ..entitas import Processors
from overrides import override
from typing import cast
from ..game.base_game import BaseGame


class TCGGameProcessPipeline(Processors):

    @staticmethod
    def create_home_state_pipline(game: BaseGame) -> "TCGGameProcessPipeline":

        ### 不这样就循环引用
        from ..game.tcg_game import TCGGame

        ## 添加一些系统。。。
        from ..tcg_game_systems.begin_system import BeginSystem
        from ..tcg_game_systems.end_system import EndSystem
        from ..tcg_game_systems.kick_off_system import KickOffSystem
        from ..tcg_game_systems.save_system import SaveSystem
        from ..tcg_game_systems.mind_voice_action_system import (
            MindVoiceActionSystem,
        )
        from ..tcg_game_systems.speak_action_system import SpeakActionSystem
        from ..tcg_game_systems.pre_action_system import PreActionSystem
        from ..tcg_game_systems.post_action_system import PostActionSystem
        from ..tcg_game_systems.destroy_entity_system import DestroyEntitySystem
        from ..tcg_game_systems.home_pre_system import HomePreSystem
        from ..tcg_game_systems.home_post_system import HomePostSystem

        from ..tcg_game_systems.home_stage_system import (
            HomeStageSystem,
        )
        from ..tcg_game_systems.home_actor_system import (
            HomeActorSystem,
        )
        from ..tcg_game_systems.whisper_action_system import WhisperActionSystem
        from ..tcg_game_systems.announce_action_system import AnnounceActionSystem

        ##
        tcg_game = cast(TCGGame, game)
        processors = TCGGameProcessPipeline()

        processors.add(BeginSystem(tcg_game))

        # 启动agent的提示词。启动阶段
        processors.add(KickOffSystem(tcg_game))

        # 规划逻辑
        ######## 在所有规划之前!##############################################################
        processors.add(HomePreSystem(tcg_game))
        processors.add(HomeStageSystem(tcg_game))
        processors.add(HomeActorSystem(tcg_game))
        processors.add(HomePostSystem(tcg_game))
        ####### 在所有规划之后! ##############################################################

        # 动作处理相关的系统 ##################################################################
        ####################################################################################
        processors.add(PreActionSystem(tcg_game))
        processors.add(MindVoiceActionSystem(tcg_game))
        processors.add(SpeakActionSystem(tcg_game))
        processors.add(WhisperActionSystem(tcg_game))
        processors.add(AnnounceActionSystem(tcg_game))
        processors.add(PostActionSystem(tcg_game))
        ####################################################################################
        ####################################################################################

        # 动作处理后，可能清理。
        processors.add(DestroyEntitySystem(tcg_game))

        # 存储系统。
        processors.add(SaveSystem(tcg_game))

        # 结束
        processors.add(EndSystem(tcg_game))

        return processors

    ###################################################################################################################################################################

    @staticmethod
    def create_dungeon_combat_state_pipeline(
        game: BaseGame,
    ) -> "TCGGameProcessPipeline":

        ### 不这样就循环引用
        from ..game.tcg_game import TCGGame

        ## 添加一些系统。。。
        from ..tcg_game_systems.begin_system import BeginSystem
        from ..tcg_game_systems.end_system import EndSystem
        from ..tcg_game_systems.kick_off_system import KickOffSystem
        from ..tcg_game_systems.save_system import SaveSystem
        from ..tcg_game_systems.pre_action_system import PreActionSystem
        from ..tcg_game_systems.post_action_system import PostActionSystem
        from ..tcg_game_systems.destroy_entity_system import DestroyEntitySystem
        from ..tcg_game_systems.combat_death_system import CombatDeathSystem
        from ..tcg_game_systems.turn_action_system import TurnActionSystem
        from ..tcg_game_systems.director_action_system import (
            DirectorActionSystem,
        )
        from ..tcg_game_systems.feedback_action_system import FeedbackActionSystem
        from ..tcg_game_systems.combat_kick_off_system import (
            CombatKickOffSystem,
        )
        from ..tcg_game_systems.combat_complete_system import (
            CombatCompleteSystem,
        )

        from ..tcg_game_systems.combat_resolution_system import (
            CombatResolutionSystem,
        )

        from ..tcg_game_systems.dungeon_stage_system import (
            DungeonStageSystem,
        )

        from ..tcg_game_systems.combat_result_system import (
            CombatResultSystem,
        )

        from ..tcg_game_systems.combat_round_system import (
            CombatRoundSystem,
        )

        from ..tcg_game_systems.draw_cards_action_system import (
            DrawCardsActionSystem,
        )

        ##
        tcg_game = cast(TCGGame, game)
        processors = TCGGameProcessPipeline()

        # 标记开始。
        processors.add(BeginSystem(tcg_game))

        # 启动agent的提示词。启动阶段
        processors.add(KickOffSystem(tcg_game))

        # 场景先规划，可能会有一些变化。
        processors.add(DungeonStageSystem(tcg_game))
        # 大状态切换：战斗触发！！
        processors.add(CombatKickOffSystem(tcg_game))
        # 大状态切换：战斗结束。
        processors.add(CombatCompleteSystem(tcg_game))
        # 自动开局
        processors.add(CombatRoundSystem(tcg_game))

        # 抽卡。
        ######动作开始！！！！！################################################################################################
        processors.add(PreActionSystem(tcg_game))
        processors.add(DrawCardsActionSystem(tcg_game))
        processors.add(TurnActionSystem(tcg_game))
        processors.add(DirectorActionSystem(tcg_game))
        processors.add(FeedbackActionSystem(tcg_game))
        processors.add(
            CombatResolutionSystem(tcg_game)
        )  # 最终将过程合成。因为中间会有很多request，防止断掉。
        processors.add(PostActionSystem(tcg_game))
        ###### 动作结束！！！！！################################################################################################

        # 检查死亡
        processors.add(CombatDeathSystem(tcg_game))
        processors.add(CombatResultSystem(tcg_game))

        # 核心系统，检查需要删除的实体。
        processors.add(DestroyEntitySystem(tcg_game))

        # 核心系统，存储系统。
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
            logger.warning(f"initialize {processor.__class__.__name__}")
            processor.initialize()

    ###################################################################################################################################################################
    ## 异步执行方法
    async def a_execute(self) -> None:
        for processor in self._execute_processors:
            logger.warning(f"a_execute {processor.__class__.__name__}")
            await processor.a_execute1()
            processor.execute()
            await processor.a_execute2()

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:
        for processor in self._execute_processors:
            logger.warning(f"execute {processor.__class__.__name__}")
            processor.execute()

    ###################################################################################################################################################################
    @override
    def tear_down(self) -> None:
        for processor in self._tear_down_processors:
            logger.warning(f"tear_down {processor.__class__.__name__}")
            processor.tear_down()


###################################################################################################################################################################
