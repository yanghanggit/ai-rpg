from typing import Any, cast
from my_entitas.extended_context import ExtendedContext
from ecs_systems.agents_kick_off_system import AgentsKickOffSystem
from ecs_systems.stage_planning_system import StagePlanningSystem
from ecs_systems.actor_planning_system import ActorPlanningSystem
from ecs_systems.speak_action_system import SpeakActionSystem
from ecs_systems.attack_action_system import AttackActionSystem
from ecs_systems.go_to_action_system import GoToActionSystem
from ecs_systems.check_before_go_to_action_system import CheckBeforeGoToActionSystem
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
from ecs_systems.post_fight_system import PostFightSystem
from ecs_systems.update_archive_system import UpdateArchiveSystem
from ecs_systems.portal_step_action_system import PortalStepActionSystem
from ecs_systems.perception_action_system import PerceptionActionSystem
from ecs_systems.steal_action_system import StealActionSystem
from ecs_systems.give_prop_action_system import GivePropActionSystem
from ecs_systems.check_status_action_system import CheckStatusActionSystem
from ecs_systems.agents_connect_system import AgentsConnectSystem
from my_entitas.extended_processors import ExtendedProcessors
from ecs_systems.simple_rpg_pre_fight_system import SimpleRPGPreFightSystem
from ecs_systems.compress_chat_history_system import CompressChatHistorySystem
from ecs_systems.post_conversation_action_system import PostConversationActionSystem
from ecs_systems.update_appearance_system import UpdateAppearanceSystem


UPDATE_APPEARANCE_SYSTEM_NAME = "角色外观生成器"

def create_rpg_processors(rpggame: Any, context: ExtendedContext) -> ExtendedProcessors:

    # 
    from ecs_systems.handle_player_input_system import HandlePlayerInputSystem ### 不这样就循环引用
    from ecs_systems.update_client_message_system import UpdateClientMessageSystem
    from ecs_systems.dead_action_system import DeadActionSystem
    from ecs_systems.terminal_player_interrupt_and_wait_system import TerminalPlayerInterruptAndWaitSystem
    from ecs_systems.terminal_player_input_system import TerminalPlayerInputSystem
    from ecs_systems.save_system import SaveSystem
    from rpg_game.rpg_game import RPGGame

    ##
    rpg_game = cast(RPGGame, rpggame)

    processors = ExtendedProcessors()
    
    ##调试用的系统。监视进入运行之前的状态
    processors.add(BeginSystem(context))
    
    #初始化系统########################
    processors.add(AgentsConnectSystem(context)) ### 连接所有agent
    processors.add(AgentsKickOffSystem(context)) ### 第一次读状态, initmemory
    processors.add(UpdateAppearanceSystem(context, UPDATE_APPEARANCE_SYSTEM_NAME)) ### 更新外观
    #########################################

    
    processors.add(HandlePlayerInputSystem(context, rpg_game)) 

    # 行动逻辑################################################################################################
    processors.add(PreActionSystem(context)) ######## 在所有行动之前 #########################################

    #交流（与说话类）的行为
    processors.add(TagActionSystem(context))
    processors.add(MindVoiceActionSystem(context))
    processors.add(WhisperActionSystem(context))
    processors.add(BroadcastActionSystem(context))
    processors.add(SpeakActionSystem(context))

    # 这里必须在所有对话之后，目前是防止用户用对话行为说出不符合政策的话
    processors.add(PostConversationActionSystem(context))

    #战斗类的行为 ##########
    processors.add(SimpleRPGPreFightSystem(context)) #战斗之前需要更新装备
    processors.add(AttackActionSystem(context)) 
    processors.add(PostFightSystem(context))

    ## 战斗类行为产生结果可能有死亡，死亡之后，后面的行为都不可以做。
    
    processors.add(DeadActionSystem(context, rpg_game)) 
    
    # 交互类的行为（交换数据），在死亡之后，因为死了就不能执行。。。
    processors.add(SearchPropActionSystem(context)) 
    processors.add(StealActionSystem(context))
    processors.add(GivePropActionSystem(context))
    processors.add(UsePropActionSystem(context))
    processors.add(CheckStatusActionSystem(context)) # 道具交互类行为之后，可以发起自检

    # 场景切换类行为，非常重要而且必须在最后
    processors.add(PortalStepActionSystem(context)) 
    # 去往场景之前的检查与实际的执行
    processors.add(CheckBeforeGoToActionSystem(context)) 
    processors.add(GoToActionSystem(context))
    #
    processors.add(PerceptionActionSystem(context)) # 场景切换类行为之后可以发起感知

    processors.add(PostActionSystem(context)) ####### 在所有行动之后 #########################################
    #########################################

    #行动结束后导演
    processors.add(StageDirectorSystem(context))
    #行动结束后更新关系网，因为依赖Director所以必须在后面
    processors.add(UpdateArchiveSystem(context))

    ###最后删除entity与存储数据
    processors.add(DestroySystem(context))
    ##测试的系统，移除掉不太重要的提示词，例如一些上行命令的。
    processors.add(CompressChatHistorySystem(context)) ## 测试的系统
    ##调试用的系统。监视进入运行之后的状态
    processors.add(EndSystem(context))

    #保存系统，在所有系统之后
    processors.add(SaveSystem(context, rpg_game))

    # 开发专用，网页版本不需要
    processors.add(TerminalPlayerInterruptAndWaitSystem(context, rpg_game))
    #########################################

    #规划逻辑########################
    processors.add(PrePlanningSystem(context)) ######## 在所有规划之前
    processors.add(StagePlanningSystem(context))
    processors.add(ActorPlanningSystem(context))
    processors.add(PostPlanningSystem(context)) ####### 在所有规划之后

    ## 第一次抓可以被player看到的信息
    processors.add(UpdateClientMessageSystem(context, rpg_game)) 

    ## 开发专用，网页版本不需要
    processors.add(TerminalPlayerInputSystem(context, rpg_game))
    
    return processors