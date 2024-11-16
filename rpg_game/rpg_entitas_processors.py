from entitas import Processors  # type: ignore
from loguru import logger
from overrides import override
import time
from typing import Any, cast
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game_config import WorldSystemNames


class RPGEntitasProcessors(Processors):

    @staticmethod
    def create(game: Any, context: RPGEntitasContext) -> "RPGEntitasProcessors":

        ### 不这样就循环引用
        from rpg_game.rpg_game import RPGGame
        from gameplay_systems.stage_planning_execution_system import (
            StagePlanningExecutionSystem,
        )
        from gameplay_systems.actor_planning_execution_system import (
            ActorPlanningExecutionSystem,
        )
        from gameplay_systems.speak_action_system import SpeakActionSystem
        from gameplay_systems.go_to_action_system import GoToActionSystem
        from gameplay_systems.stage_validator_system import StageValidatorSystem
        from gameplay_systems.stage_departure_checker_system import (
            StageDepartureCheckerSystem,
        )
        from gameplay_systems.stage_entrance_checker_system import (
            StageEntranceCheckerSystem,
        )

        from gameplay_systems.destroy_entity_system import DestroyEntitySystem
        from gameplay_systems.tag_action_system import TagActionSystem
        from gameplay_systems.announce_action_system import AnnounceActionSystem
        from gameplay_systems.whisper_action_system import WhisperActionSystem
        from gameplay_systems.mind_voice_action_system import MindVoiceActionSystem
        from gameplay_systems.begin_system import BeginSystem
        from gameplay_systems.end_system import EndSystem
        from gameplay_systems.pre_planning_system import PrePlanningSystem
        from gameplay_systems.stage_planning_strategy_system import (
            StagePlanningStrategySystem,
        )
        from gameplay_systems.actor_planning_strategy_system import (
            ActorPlanningStrategySystem,
        )

        from gameplay_systems.post_planning_system import PostPlanningSystem
        from gameplay_systems.pre_action_system import PreActionSystem
        from gameplay_systems.post_action_system import PostActionSystem
        from gameplay_systems.steal_action_system import StealActionSystem
        from gameplay_systems.give_prop_action_system import GivePropActionSystem
        from gameplay_systems.agent_connect_system import AgentConnectSystem
        from gameplay_systems.compress_chat_history_system import (
            CompressChatHistorySystem,
        )
        from gameplay_systems.post_conversation_action_system import (
            PostConversationActionSystem,
        )
        from gameplay_systems.pre_conversation_action_system import (
            PreConversationActionSystem,
        )
        from gameplay_systems.update_appearance_action_system import (
            UpdateAppearanceActionSystem,
        )
        from gameplay_systems.stage_narrate_action_system import (
            StageNarrateActionSystem,
        )
        from gameplay_systems.skill_invocation_system import (
            SkillInvocationSystem,
        )
        from gameplay_systems.skill_impact_response_evaluator_system import (
            SkillImpactResponseEvaluatorSystem,
        )
        from gameplay_systems.damage_action_system import DamageActionSystem
        from gameplay_systems.handle_terminal_player_input_system import (
            HandleTerminalPlayerInputSystem,
        )
        from gameplay_systems.update_client_message_system import (
            UpdateClientMessageSystem,
        )
        from gameplay_systems.dead_action_system import DeadActionSystem
        from gameplay_systems.terminal_player_interrupt_wait_system import (
            TerminalPlayerInterruptWaitSystem,
        )

        from gameplay_systems.agent_kick_off_system import AgentKickOffSystem
        from gameplay_systems.update_archive_system import UpdateArchiveSystem
        from gameplay_systems.terminal_player_tips_system import (
            TerminalPlayerTipsSystem,
        )
        from gameplay_systems.equip_prop_action_system import EquipPropActionSystem
        from gameplay_systems.skill_readiness_validator_system import (
            SkillReadinessValidatorSystem,
        )
        from gameplay_systems.skill_world_harmony_inspector_system import (
            SkillWorldHarmonyInspectorSystem,
        )
        from gameplay_systems.save_game_resource_system import SaveGameResourceSystem
        from gameplay_systems.save_entity_system import SaveEntitySystem
        from gameplay_systems.save_player_system import SavePlayerSystem
        from gameplay_systems.web_player_tips_system import WebPlayerTipsSystem
        from gameplay_systems.stage_spawner_system import StageSpawnerSystem
        from gameplay_systems.game_round_system import GameRoundSystem
        from gameplay_systems.handle_web_player_input_system import (
            HandleWebPlayerInputSystem,
        )

        ##
        rpg_game = cast(RPGGame, game)

        processors = RPGEntitasProcessors()

        # 初始化系统########################
        processors.add(
            StageSpawnerSystem(context, rpg_game)
        )  # 因为需要connect 与 kick off，所以需要放在2者之前
        processors.add(AgentConnectSystem(context, rpg_game))
        processors.add(AgentKickOffSystem(context, rpg_game))
        #########################################

        # 游戏回合系统，就是计算游戏的时间这个开始问题
        processors.add(GameRoundSystem(context, rpg_game))

        ##调试用的系统。监视进入运行之前的状态
        processors.add(BeginSystem(context, rpg_game))

        ### 处理玩家输入!
        processors.add(HandleTerminalPlayerInputSystem(context, rpg_game))
        processors.add(HandleWebPlayerInputSystem(context, rpg_game))

        # 行动逻辑!
        processors.add(
            PreActionSystem(context, rpg_game)
        )  ######## <在所有行动之前> ##############################################################

        processors.add(
            UpdateAppearanceActionSystem(
                context,
                rpg_game,
                WorldSystemNames.WORLD_APPEARANCE_SYSTEM_NAME,
            )
        )  ### 更新外观

        # 交流（与说话类）的行为!
        processors.add(
            PreConversationActionSystem(context, rpg_game)
        )  # 所有对话之前目前是防止用户用对话行为说出不符合政策的话
        processors.add(StageNarrateActionSystem(context, rpg_game))
        processors.add(TagActionSystem(context, rpg_game))
        processors.add(MindVoiceActionSystem(context, rpg_game))
        processors.add(WhisperActionSystem(context, rpg_game))
        processors.add(AnnounceActionSystem(context, rpg_game))
        processors.add(SpeakActionSystem(context, rpg_game))
        processors.add(PostConversationActionSystem(context, rpg_game))

        # 战斗类的行为!
        processors.add(SkillInvocationSystem(context, rpg_game))
        processors.add(SkillReadinessValidatorSystem(context, rpg_game))
        processors.add(
            SkillWorldHarmonyInspectorSystem(
                context, rpg_game, WorldSystemNames.WORLD_SKILL_SYSTEM_NAME
            )
        )

        processors.add(SkillImpactResponseEvaluatorSystem(context, rpg_game))
        processors.add(DamageActionSystem(context, rpg_game))
        processors.add(
            DeadActionSystem(context, rpg_game)
        )  ## 战斗类行为产生结果可能有死亡，死亡之后，后面的行为都不可以做。

        # 交互类的行为（交换数据），在死亡之后，因为死了就不能执行
        processors.add(StealActionSystem(context, rpg_game))
        processors.add(GivePropActionSystem(context, rpg_game))
        processors.add(EquipPropActionSystem(context, rpg_game))
        processors.add(
            UpdateAppearanceActionSystem(
                context,
                rpg_game,
                WorldSystemNames.WORLD_APPEARANCE_SYSTEM_NAME,
            )
        )  ### 更新外观

        # 场景切换类行为，非常重要而且必须在最后，在正式执行之前有3个系统负责检查与提示。
        processors.add(StageValidatorSystem(context, rpg_game))
        processors.add(StageDepartureCheckerSystem(context, rpg_game))
        processors.add(StageEntranceCheckerSystem(context, rpg_game))
        processors.add(GoToActionSystem(context, rpg_game))

        processors.add(
            PostActionSystem(context, rpg_game)
        )  ####### <在所有行动之后> ##############################################################

        # 更新档案
        processors.add(UpdateArchiveSystem(context, rpg_game))

        ###最后删除entity与存储数据
        processors.add(DestroyEntitySystem(context, rpg_game))

        ##测试的系统，移除掉不太重要的提示词，例如一些上行命令的。
        processors.add(CompressChatHistorySystem(context, rpg_game))  ## 测试的系统

        ##调试用的系统。监视进入运行之后的状态
        processors.add(EndSystem(context, rpg_game))

        # 存储系统
        processors.add(SaveEntitySystem(context, rpg_game))
        processors.add(SaveGameResourceSystem(context, rpg_game))

        # 开发专用，网页版本不需要
        processors.add(TerminalPlayerInterruptWaitSystem(context, rpg_game))

        # 规划逻辑
        processors.add(PrePlanningSystem(context, rpg_game))  ######## 在所有规划之前!

        processors.add(StagePlanningStrategySystem(context, rpg_game))
        processors.add(ActorPlanningStrategySystem(context, rpg_game))

        processors.add(StagePlanningExecutionSystem(context, rpg_game))
        processors.add(ActorPlanningExecutionSystem(context, rpg_game))
        processors.add(PostPlanningSystem(context, rpg_game))  ####### 在所有规划之后!

        ## 第一次抓可以被player看到的信息
        processors.add(UpdateClientMessageSystem(context, rpg_game))
        processors.add(TerminalPlayerTipsSystem(context, rpg_game))
        processors.add(WebPlayerTipsSystem(context, rpg_game))

        # 在这里记录，不然少message
        processors.add(SavePlayerSystem(context, rpg_game))

        return processors

    ###################################################################################################################################################################
    def __init__(self) -> None:
        super().__init__()
        self._initialized: bool = False

    ###################################################################################################################################################################
    @override
    def initialize(self) -> None:

        for processor in self._initialize_processors:
            logger.debug(
                f"<<<<<<<<<<<<< initialize: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>"
            )
            start_time = time.time()

            processor.initialize()

            end_time = time.time()
            execution_time = end_time - start_time
            logger.debug(
                f"{processor.__class__.__name__} initialize time: {execution_time:.2f} seconds"
            )

    ###################################################################################################################################################################
    ## 异步执行方法
    async def a_execute(self) -> None:
        for processor in self._execute_processors:

            logger.debug(
                f"<<<<<<<<<<<<< execute: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>"
            )
            start_time = time.time()

            await processor.a_execute1()
            processor.execute()
            await processor.a_execute2()

            end_time = time.time()
            execution_time = end_time - start_time
            logger.debug(
                f"{processor.__class__.__name__} execute time: {execution_time:.2f} seconds"
            )

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:
        for processor in self._execute_processors:

            logger.debug(
                f"<<<<<<<<<<<<< execute: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>"
            )
            start_time = time.time()

            processor.execute()

            end_time = time.time()
            execution_time = end_time - start_time
            logger.debug(
                f"{processor.__class__.__name__} execute time: {execution_time:.2f} seconds"
            )

    ###################################################################################################################################################################
    @override
    def tear_down(self) -> None:
        for processor in self._tear_down_processors:

            logger.debug(
                f"<<<<<<<<<<<<< tear_down: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>"
            )
            processor.tear_down()


###################################################################################################################################################################
