from entitas import Processors  # type: ignore
from loguru import logger
from overrides import override
import time
from typing import Any, cast
from rpg_game.rpg_entitas_context import RPGEntitasContext
import rpg_game.rpg_entitas_builtin_world_system as builtin_world_systems


class RPGEntitasProcessors(Processors):

    @staticmethod
    def create(
        input_rpg_game: Any, context: RPGEntitasContext
    ) -> "RPGEntitasProcessors":

        ### 不这样就循环引用
        from rpg_game.rpg_game import RPGGame
        from gameplay_systems.stage_planning_system import StagePlanningSystem
        from gameplay_systems.actor_planning_system import ActorPlanningSystem
        from gameplay_systems.speak_action_system import SpeakActionSystem
        from gameplay_systems.go_to_action_system import GoToActionSystem
        from gameplay_systems.pre_go_to_action_system import PreBeforeGoToActionSystem
        from gameplay_systems.destroy_entity_system import DestroyEntitySystem
        from gameplay_systems.tag_action_system import TagActionSystem
        from gameplay_systems.broadcast_action_system import BroadcastActionSystem
        from gameplay_systems.whisper_action_system import WhisperActionSystem
        from gameplay_systems.pick_up_prop_action_system import PickUpPropActionSystem
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
        from gameplay_systems.connect_agent_system import ConnectAgentSystem
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
        from gameplay_systems.behavior_action_system import BehaviorActionSystem
        from gameplay_systems.skill_action_system import SkillActionSystem
        from gameplay_systems.damage_action_system import DamageActionSystem
        from gameplay_systems.handle_player_input_system import HandlePlayerInputSystem
        from gameplay_systems.update_client_message_system import (
            UpdateClientMessageSystem,
        )
        from gameplay_systems.dead_action_system import DeadActionSystem
        from gameplay_systems.terminal_player_interrupt_and_wait_system import (
            TerminalPlayerInterruptAndWaitSystem,
        )
        from gameplay_systems.terminal_player_input_system import (
            TerminalPlayerInputSystem,
        )
        from gameplay_systems.save_system import SaveSystem
        from gameplay_systems.agent_kick_off_system import AgentKickOffSystem
        from gameplay_systems.update_archive_system import UpdateArchiveSystem
        from gameplay_systems.terminal_player_tips_system import (
            TerminalPlayerTipsSystem,
        )
        from gameplay_systems.equip_prop_action_system import EquipPropActionSystem
        from gameplay_systems.remove_prop_action_system import (
            RemovePropActionSystem,
        )

        ##
        input_rpg_game = cast(RPGGame, input_rpg_game)

        processors = RPGEntitasProcessors()

        ##调试用的系统。监视进入运行之前的状态
        processors.add(BeginSystem(context, input_rpg_game))

        # 初始化系统########################
        processors.add(ConnectAgentSystem(context, input_rpg_game))
        processors.add(AgentKickOffSystem(context, input_rpg_game))
        #########################################

        ### 处理玩家输入!
        processors.add(HandlePlayerInputSystem(context, input_rpg_game))

        # 行动逻辑!
        processors.add(
            PreActionSystem(context, input_rpg_game)
        )  ######## <在所有行动之前> ##############################################################

        processors.add(
            UpdateAppearanceActionSystem(
                context,
                input_rpg_game,
                builtin_world_systems.WORLD_APPEARANCE_SYSTEM_NAME,
            )
        )  ### 更新外观

        # 交流（与说话类）的行为!
        processors.add(
            PreConversationActionSystem(context, input_rpg_game)
        )  # 所有对话之前
        processors.add(StageNarrateActionSystem(context, input_rpg_game))
        processors.add(TagActionSystem(context, input_rpg_game))
        processors.add(MindVoiceActionSystem(context, input_rpg_game))
        processors.add(WhisperActionSystem(context, input_rpg_game))
        processors.add(BroadcastActionSystem(context, input_rpg_game))
        processors.add(SpeakActionSystem(context, input_rpg_game))
        processors.add(
            PostConversationActionSystem(context, input_rpg_game)
        )  # 所有对话之后，目前是防止用户用对话行为说出不符合政策的话

        # 战斗类的行为!
        processors.add(BehaviorActionSystem(context, input_rpg_game))
        processors.add(
            SkillActionSystem(
                context, input_rpg_game, builtin_world_systems.WORLD_SKILL_SYSTEM_NAME
            )
        )
        processors.add(DamageActionSystem(context, input_rpg_game))
        processors.add(
            DeadActionSystem(context, input_rpg_game)
        )  ## 战斗类行为产生结果可能有死亡，死亡之后，后面的行为都不可以做。

        # 交互类的行为（交换数据），在死亡之后，因为死了就不能执行
        processors.add(PickUpPropActionSystem(context, input_rpg_game))
        processors.add(StealActionSystem(context, input_rpg_game))
        processors.add(GivePropActionSystem(context, input_rpg_game))
        processors.add(EquipPropActionSystem(context, input_rpg_game))
        processors.add(
            UpdateAppearanceActionSystem(
                context,
                input_rpg_game,
                builtin_world_systems.WORLD_APPEARANCE_SYSTEM_NAME,
            )
        )  ### 更新外观
        processors.add(RemovePropActionSystem(context, input_rpg_game))

        # 场景切换类行为，非常重要而且必须在最后!
        processors.add(
            PreBeforeGoToActionSystem(context, input_rpg_game)
        )  # 去往场景之前的检查与实际的执行
        processors.add(GoToActionSystem(context, input_rpg_game))

        processors.add(
            PostActionSystem(context, input_rpg_game)
        )  ####### <在所有行动之后> ##############################################################

        # 更新档案
        processors.add(UpdateArchiveSystem(context, input_rpg_game))

        ###最后删除entity与存储数据
        processors.add(DestroyEntitySystem(context, input_rpg_game))

        ##测试的系统，移除掉不太重要的提示词，例如一些上行命令的。
        processors.add(
            CompressChatHistorySystem(context, input_rpg_game)
        )  ## 测试的系统

        ##调试用的系统。监视进入运行之后的状态
        processors.add(EndSystem(context, input_rpg_game))

        # 保存系统，在所有系统之后
        processors.add(SaveSystem(context, input_rpg_game))

        # 开发专用，网页版本不需要
        processors.add(TerminalPlayerInterruptAndWaitSystem(context, input_rpg_game))

        # 规划逻辑
        processors.add(
            PrePlanningSystem(context, input_rpg_game)
        )  ######## 在所有规划之前!

        processors.add(StagePlanningStrategySystem(context, input_rpg_game))
        processors.add(ActorPlanningStrategySystem(context, input_rpg_game))

        processors.add(StagePlanningSystem(context, input_rpg_game))
        processors.add(ActorPlanningSystem(context, input_rpg_game))
        processors.add(
            PostPlanningSystem(context, input_rpg_game)
        )  ####### 在所有规划之后!

        ## 第一次抓可以被player看到的信息
        processors.add(UpdateClientMessageSystem(context, input_rpg_game))
        processors.add(TerminalPlayerTipsSystem(context, input_rpg_game))

        ## 开发专用，网页版本不需要
        processors.add(TerminalPlayerInputSystem(context, input_rpg_game))

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
