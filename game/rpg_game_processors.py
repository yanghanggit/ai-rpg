from entitas import Processors  # type: ignore
from overrides import override
from typing import cast
from game.rpg_game_context import RPGGameContext
from game.rpg_game_config import WorldSystemNames
from game.base_game import BaseGame


class RPGGameProcessors(Processors):

    @staticmethod
    def create(game: BaseGame, context: RPGGameContext) -> "RPGGameProcessors":

        ### 不这样就循环引用
        from game.rpg_game import RPGGame
        from rpg_game_systems.stage_planning_execution_system import (
            StagePlanningExecutionSystem,
        )
        from rpg_game_systems.actor_planning_execution_system import (
            ActorPlanningExecutionSystem,
        )
        from rpg_game_systems.speak_action_system import SpeakActionSystem
        from rpg_game_systems.go_to_action_system import GoToActionSystem
        from rpg_game_systems.stage_validator_system import StageValidatorSystem
        from rpg_game_systems.stage_departure_checker_system import (
            StageDepartureCheckerSystem,
        )
        from rpg_game_systems.stage_entrance_checker_system import (
            StageEntranceCheckerSystem,
        )

        from rpg_game_systems.destroy_entity_system import DestroyEntitySystem
        from rpg_game_systems.tag_action_system import TagActionSystem
        from rpg_game_systems.announce_action_system import AnnounceActionSystem
        from rpg_game_systems.whisper_action_system import WhisperActionSystem
        from rpg_game_systems.mind_voice_action_system import MindVoiceActionSystem
        from rpg_game_systems.begin_system import BeginSystem
        from rpg_game_systems.end_system import EndSystem
        from rpg_game_systems.pre_planning_system import PrePlanningSystem
        from rpg_game_systems.stage_planning_strategy_system import (
            StagePlanningStrategySystem,
        )
        from rpg_game_systems.actor_planning_strategy_system import (
            ActorPlanningStrategySystem,
        )

        from rpg_game_systems.post_planning_system import PostPlanningSystem
        from rpg_game_systems.pre_action_system import PreActionSystem
        from rpg_game_systems.post_action_system import PostActionSystem
        from rpg_game_systems.steal_prop_action_system import StealPropActionSystem
        from rpg_game_systems.transfer_prop_action_system import (
            TransferPropActionSystem,
        )
        from rpg_game_systems.agent_ping_validator_system import (
            AgentPingValidatorSystem,
        )
        from rpg_game_systems.compress_chat_history_system import (
            CompressChatHistorySystem,
        )
        from rpg_game_systems.post_conversation_action_system import (
            PostConversationActionSystem,
        )
        from rpg_game_systems.pre_conversation_action_system import (
            PreConversationActionSystem,
        )
        from rpg_game_systems.update_appearance_action_system import (
            UpdateAppearanceActionSystem,
        )
        from rpg_game_systems.stage_narrate_action_system import (
            StageNarrateActionSystem,
        )
        from rpg_game_systems.skill_invocation_system import (
            SkillInvocationSystem,
        )

        # from rpg_game_systems.skill_hit_impact_system import (
        #     SkillHitImpactSystem,
        # )
        # from rpg_game_systems.damage_action_system import DamageActionSystem
        from rpg_game_systems.handle_terminal_player_input_system import (
            HandleTerminalPlayerInputSystem,
        )
        from rpg_game_systems.update_client_message_system import (
            UpdateClientMessageSystem,
        )

        # from rpg_game_systems.dead_action_system import DeadActionSystem
        from rpg_game_systems.terminal_player_interrupt_wait_system import (
            TerminalPlayerInterruptWaitSystem,
        )

        from rpg_game_systems.agent_kick_off_system import AgentKickOffSystem
        from rpg_game_systems.update_archive_system import UpdateArchiveSystem
        from rpg_game_systems.terminal_player_tips_system import (
            TerminalPlayerTipsSystem,
        )
        from rpg_game_systems.equip_prop_action_system import EquipPropActionSystem

        # from rpg_game_systems.skill_readiness_validator_system import (
        #     SkillReadinessValidatorSystem,
        # )
        # from rpg_game_systems.skill_world_harmony_inspector_system import (
        #     SkillWorldHarmonyInspectorSystem,
        # )
        from rpg_game_systems.save_game_resource_system import SaveGameResourceSystem
        from rpg_game_systems.save_entity_system import SaveEntitySystem
        from rpg_game_systems.save_player_system import SavePlayerSystem
        from rpg_game_systems.web_player_tips_system import WebPlayerTipsSystem
        from rpg_game_systems.stage_spawner_system import StageSpawnerSystem
        from rpg_game_systems.game_round_system import GameRoundSystem
        from rpg_game_systems.handle_web_player_input_system import (
            HandleWebPlayerInputSystem,
        )
        from rpg_game_systems.stage_tag_action_system import StageTagActionSystem
        from rpg_game_systems.inspect_action_system import InspectActionSystem

        # from rpg_game_systems.stage_transfer_action_system import (
        #     StageTransferActionSystem,
        # )
        # from rpg_game_systems.skill_feedback_system import SkillFeedbackSystem
        # from rpg_game_systems.heal_action_system import HealActionSystem

        ##
        rpg_game = cast(RPGGame, game)

        processors = RPGGameProcessors()

        # 初始化系统########################
        processors.add(
            StageSpawnerSystem(context, rpg_game)
        )  # 因为需要connect 与 kick off，所以需要放在2者之前
        processors.add(AgentPingValidatorSystem(context, rpg_game))
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

        # 第一次更新外观！基本就是kickoff 用
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
        processors.add(StageTagActionSystem(context, rpg_game))
        processors.add(StageNarrateActionSystem(context, rpg_game))
        processors.add(TagActionSystem(context, rpg_game))
        processors.add(MindVoiceActionSystem(context, rpg_game))
        processors.add(WhisperActionSystem(context, rpg_game))
        processors.add(AnnounceActionSystem(context, rpg_game))
        processors.add(SpeakActionSystem(context, rpg_game))
        processors.add(PostConversationActionSystem(context, rpg_game))

        ### 正式的更新外观
        processors.add(EquipPropActionSystem(context, rpg_game))
        processors.add(
            UpdateAppearanceActionSystem(
                context,
                rpg_game,
                WorldSystemNames.WORLD_APPEARANCE_SYSTEM_NAME,
            )
        )

        # 战斗类的行为!
        processors.add(SkillInvocationSystem(context, rpg_game))

        ### SkillInvocationSystem里，可能会切换武器
        processors.add(EquipPropActionSystem(context, rpg_game))
        processors.add(
            UpdateAppearanceActionSystem(
                context,
                rpg_game,
                WorldSystemNames.WORLD_APPEARANCE_SYSTEM_NAME,
            )
        )

        # processors.add(SkillReadinessValidatorSystem(context, rpg_game))
        # processors.add(
        #     SkillWorldHarmonyInspectorSystem(
        #         context, rpg_game, WorldSystemNames.WORLD_SKILL_SYSTEM_NAME
        #     )
        # )

        # processors.add(SkillHitImpactSystem(context, rpg_game))
        # processors.add(HealActionSystem(context, rpg_game))  # 先治疗后伤害。
        # processors.add(DamageActionSystem(context, rpg_game))
        # processors.add(
        #     SkillFeedbackSystem(context, rpg_game)
        # )  # 一些特殊事件的反馈。可能触发 StageTransfer
        # processors.add(StageTransferActionSystem(context, rpg_game))
        # processors.add(
        #     DeadActionSystem(context, rpg_game)
        # )  ## 战斗类行为产生结果可能有死亡，死亡之后，后面的行为都不可以做。

        # 交互类的行为（交换数据），在死亡之后，因为死了就不能执行
        processors.add(StealPropActionSystem(context, rpg_game))
        processors.add(TransferPropActionSystem(context, rpg_game))
        # 检查与提示类行为，临时放在这个位置。
        processors.add(InspectActionSystem(context, rpg_game))

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
            # logger.debug(
            #     f"<<<<<<<<<<<<< initialize: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>"
            # )
            # start_time = time.time()

            processor.initialize()

            # end_time = time.time()
            # execution_time = end_time - start_time
            # logger.debug(
            #     f"{processor.__class__.__name__} initialize time: {execution_time:.2f} seconds"
            # )

    ###################################################################################################################################################################
    ## 异步执行方法
    async def a_execute(self) -> None:
        for processor in self._execute_processors:

            # logger.debug(
            #     f"<<<<<<<<<<<<< execute: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>"
            # )
            # start_time = time.time()

            await processor.a_execute1()
            processor.execute()
            await processor.a_execute2()

            # end_time = time.time()
            # execution_time = end_time - start_time
            # logger.debug(
            #     f"{processor.__class__.__name__} execute time: {execution_time:.2f} seconds"
            # )

    ###################################################################################################################################################################
    @override
    def execute(self) -> None:
        for processor in self._execute_processors:

            # logger.debug(
            #     f"<<<<<<<<<<<<< execute: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>"
            # )
            # start_time = time.time()

            processor.execute()

            # end_time = time.time()
            # execution_time = end_time - start_time
            # logger.debug(
            #     f"{processor.__class__.__name__} execute time: {execution_time:.2f} seconds"
            # )

    ###################################################################################################################################################################
    @override
    def tear_down(self) -> None:
        for processor in self._tear_down_processors:

            # logger.debug(
            #     f"<<<<<<<<<<<<< tear_down: {processor.__class__.__name__}  >>>>>>>>>>>>>>>>>"
            # )
            processor.tear_down()


###################################################################################################################################################################
