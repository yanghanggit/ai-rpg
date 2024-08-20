from entitas import Processors  # type: ignore
from loguru import logger
from overrides import override
import time
from typing import Any, cast
from rpg_game.rpg_entitas_context import RPGEntitasContext
from ecs_systems.stage_planning_system import StagePlanningSystem
from ecs_systems.actor_planning_system import ActorPlanningSystem
from ecs_systems.speak_action_system import SpeakActionSystem
from ecs_systems.attack_action_system import AttackActionSystem
from ecs_systems.go_to_action_system import GoToActionSystem
from ecs_systems.pre_go_to_action_system import PreBeforeGoToActionSystem
from ecs_systems.stage_director_system import StageDirectorSystem
from ecs_systems.destroy_system import DestroySystem
from ecs_systems.tag_action_system import TagActionSystem
from ecs_systems.broadcast_action_system import BroadcastActionSystem
from ecs_systems.use_prop_action_system import UsePropActionSystem
from ecs_systems.whisper_action_system import WhisperActionSystem
from ecs_systems.search_prop_action_system import SearchPropActionSystem
from ecs_systems.mind_voice_action_system import MindVoiceActionSystem
from ecs_systems.begin_system import BeginSystem
from ecs_systems.end_system import EndSystem
from ecs_systems.pre_planning_system import PrePlanningSystem
from ecs_systems.post_planning_system import PostPlanningSystem
from ecs_systems.pre_action_system import PreActionSystem
from ecs_systems.post_action_system import PostActionSystem
from ecs_systems.perception_action_system import PerceptionActionSystem
from ecs_systems.steal_action_system import StealActionSystem
from ecs_systems.give_prop_action_system import GivePropActionSystem
from ecs_systems.check_status_action_system import CheckStatusActionSystem
from ecs_systems.connect_agent_system import ConnectAgentSystem
from ecs_systems.simple_rpg_pre_fight_system import SimpleRPGPreFightSystem
from ecs_systems.compress_chat_history_system import CompressChatHistorySystem
from ecs_systems.post_conversation_action_system import PostConversationActionSystem
from ecs_systems.pre_conversation_action_system import PreConversationActionSystem
from ecs_systems.update_appearance_system import UpdateAppearanceSystem
from ecs_systems.stage_narrate_action_system import StageNarrateActionSystem
from ecs_systems.behavior_action_system import BehaviorActionSystem

UPDATE_APPEARANCE_SYSTEM_NAME = "角色外观生成器"


class RPGEntitasProcessors(Processors):

    @staticmethod
    def create(rpg_game: Any, context: RPGEntitasContext) -> "RPGEntitasProcessors":

        ### 不这样就循环引用
        from ecs_systems.handle_player_input_system import HandlePlayerInputSystem
        from ecs_systems.update_client_message_system import UpdateClientMessageSystem
        from ecs_systems.dead_action_system import DeadActionSystem
        from ecs_systems.terminal_player_interrupt_and_wait_system import (
            TerminalPlayerInterruptAndWaitSystem,
        )
        from ecs_systems.terminal_player_input_system import TerminalPlayerInputSystem
        from ecs_systems.save_system import SaveSystem
        from rpg_game.rpg_game import RPGGame
        from ecs_systems.kick_off_system import KickOffSystem
        from ecs_systems.update_archive_system import UpdateArchiveSystem
        from ecs_systems.terminal_player_tips_system import TerminalPlayerTipsSystem

        ##
        rpg_game = cast(RPGGame, rpg_game)

        processors = RPGEntitasProcessors()

        ##调试用的系统。监视进入运行之前的状态
        processors.add(BeginSystem(context))

        # 初始化系统########################
        processors.add(ConnectAgentSystem(context))  ### 连接所有agent
        processors.add(KickOffSystem(context, rpg_game))  ### 第一次读状态, initmemory
        processors.add(
            UpdateAppearanceSystem(context, UPDATE_APPEARANCE_SYSTEM_NAME)
        )  ### 更新外观
        #########################################

        ### 处理玩家输入!
        processors.add(HandlePlayerInputSystem(context, rpg_game))

        # 行动逻辑!
        processors.add(
            PreActionSystem(context)
        )  ######## <在所有行动之前> ##############################################################

        # 交流（与说话类）的行为!
        processors.add(PreConversationActionSystem(context))  # 所有对话之前
        processors.add(StageNarrateActionSystem(context))
        processors.add(TagActionSystem(context))
        processors.add(MindVoiceActionSystem(context))
        processors.add(WhisperActionSystem(context))
        processors.add(BroadcastActionSystem(context))
        processors.add(SpeakActionSystem(context))
        processors.add(
            PostConversationActionSystem(context)
        )  # 所有对话之后，目前是防止用户用对话行为说出不符合政策的话

        # 战斗类的行为!
        processors.add(SimpleRPGPreFightSystem(context))
        processors.add(AttackActionSystem(context))
        processors.add(
            DeadActionSystem(context, rpg_game)
        )  ## 战斗类行为产生结果可能有死亡，死亡之后，后面的行为都不可以做。

        # 测试的系统
        processors.add(BehaviorActionSystem(context))

        # 交互类的行为（交换数据），在死亡之后，因为死了就不能执行
        processors.add(SearchPropActionSystem(context))
        processors.add(StealActionSystem(context))
        processors.add(GivePropActionSystem(context))
        processors.add(UsePropActionSystem(context))
        processors.add(
            CheckStatusActionSystem(context)
        )  # 道具交互类行为之后，可以发起自检

        # 场景切换类行为，非常重要而且必须在最后!
        processors.add(
            PreBeforeGoToActionSystem(context)
        )  # 去往场景之前的检查与实际的执行
        processors.add(GoToActionSystem(context))
        processors.add(
            PerceptionActionSystem(context)
        )  # 场景切换类行为之后可以发起感知

        processors.add(
            PostActionSystem(context)
        )  ####### <在所有行动之后> ##############################################################

        # 行动结束后导演
        processors.add(StageDirectorSystem(context))

        # 行动结束后更新关系网，因为依赖Director所以必须在后面
        processors.add(UpdateArchiveSystem(context, rpg_game))

        ###最后删除entity与存储数据
        processors.add(DestroySystem(context))

        ##测试的系统，移除掉不太重要的提示词，例如一些上行命令的。
        processors.add(CompressChatHistorySystem(context))  ## 测试的系统

        ##调试用的系统。监视进入运行之后的状态
        processors.add(EndSystem(context))

        # 保存系统，在所有系统之后
        processors.add(SaveSystem(context, rpg_game))

        # 开发专用，网页版本不需要
        processors.add(TerminalPlayerInterruptAndWaitSystem(context, rpg_game))

        # 规划逻辑
        processors.add(PrePlanningSystem(context))  ######## 在所有规划之前!
        processors.add(StagePlanningSystem(context))
        processors.add(ActorPlanningSystem(context))
        processors.add(PostPlanningSystem(context))  ####### 在所有规划之后!

        ## 第一次抓可以被player看到的信息
        processors.add(UpdateClientMessageSystem(context, rpg_game))
        processors.add(TerminalPlayerTipsSystem(context, rpg_game))

        ## 开发专用，网页版本不需要
        processors.add(TerminalPlayerInputSystem(context, rpg_game))

        return processors

    ###################################################################################################################################################################
    def __init__(self) -> None:
        super().__init__()

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

            await processor.async_pre_execute()
            processor.execute()
            await processor.async_post_execute()

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
