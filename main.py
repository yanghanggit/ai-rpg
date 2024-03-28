import os
from typing import List, Optional, Union
from entitas import Processors #type: ignore
from loguru import logger
import datetime
from auxiliary.components import (
    BroadcastActionComponent, 
    SpeakActionComponent, 
    WorldComponent,
    StageComponent, 
    NPCComponent, 
    FightActionComponent, 
    PlayerComponent, 
    SimpleRPGRoleComponent, 
    LeaveForActionComponent, 
    HumanInterferenceComponent,
    UniquePropComponent,
    BackpackComponent,
    StageEntryConditionComponent,
    StageExitConditionComponent,
    WhisperActionComponent,
    SearchActionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.actor_agent import ActorAgent
from auxiliary.extended_context import ExtendedContext
from auxiliary.dialogue_rule import parse_command, parse_target_and_message_by_symbol
from auxiliary.world_data_builder import WorldDataBuilder, AdminNpcBuilder, StageBuilder, PlayerNpcBuilder, NpcBuilder
from entitas.entity import Entity
from systems.init_system import InitSystem
from systems.stage_plan_system import StagePlanSystem
from systems.npc_plan_system import NPCPlanSystem
from systems.speak_action_system import SpeakActionSystem
from systems.fight_action_system import FightActionSystem
from systems.leave_for_action_system import LeaveForActionSystem
from systems.director_system import DirectorSystem
from systems.dead_action_system import DeadActionSystem
from systems.destroy_system import DestroySystem
from systems.tag_action_system import TagActionSystem
from systems.data_save_system import DataSaveSystem
from systems.broadcast_action_system import BroadcastActionSystem  
from systems.whisper_action_system import WhisperActionSystem 
from systems.search_props_system import SearchPropsSystem
from systems.mind_voice_action_system import MindVoiceActionSystem

from langchain_core.messages import (
    HumanMessage,
    AIMessage)


###############################################################################################################################################
def create_admin_npc_entities(context: ExtendedContext, admin_npc_builder: AdminNpcBuilder) -> List[Entity]:
    res: List[Entity] = []
    if context is None or admin_npc_builder.data is None:
        logger.error("没有AdminNpcBuilder数据，请检查World.json配置。")
        return res
    
    for admin_npc in admin_npc_builder.npcs:
        admin_npc_entity = context.create_entity()
        res.append(admin_npc_entity)

        admin_npc_agent = ActorAgent(admin_npc.name, admin_npc.url, admin_npc.memory)
        admin_npc_entity.add(WorldComponent, admin_npc_agent.name, admin_npc_agent)
        logger.debug(f"创建Admin npc：{admin_npc.name}")
        
    return res
###############################################################################################################################################
def create_player_npc_entities(context: ExtendedContext, player_npc_builder: PlayerNpcBuilder) -> List[Entity]:
    res: List[Entity] = []
    if player_npc_builder.data is None:
        logger.error("没有PlayerNpcBuilder数据，请检查World.json配置。")
        return res
    
    for player_npc in player_npc_builder.npcs:
        player_npc_entity = context.create_entity()
        res.append(player_npc_entity)

        player_npc_agent = ActorAgent(player_npc.name, player_npc.url, player_npc.memory)
        player_npc_entity.add(PlayerComponent, player_npc.name)
        player_npc_entity.add(SimpleRPGRoleComponent, player_npc.name, 10000, 10000, 10, "")
        player_npc_entity.add(NPCComponent, player_npc.name, player_npc_agent, "")
        player_npc_entity.add(BackpackComponent, player_npc.name)
        context.file_system.init_backpack_component(player_npc_entity.get(BackpackComponent))
        logger.debug(f"创建Player npc：{player_npc.name}")
        if len(player_npc.props) > 0:
            for prop in player_npc.props:
                context.file_system.add_content_into_backpack(player_npc_entity.get(BackpackComponent), prop.name)
                logger.debug(f"{player_npc.name}的背包中有：{prop.name}")

    return res
###############################################################################################################################################
def create_npc_entities(context: ExtendedContext, npc_builder: NpcBuilder) -> List[Entity]:
    res: List[Entity] = []
    if npc_builder.data is None:
        logger.error("没有NpcBuilder数据，请检查World.json配置。")
        return res
    
    for npc_in_builder in npc_builder.npcs:
        npc_entity_in_builder = context.create_entity()
        res.append(npc_entity_in_builder)

        npc_agent = ActorAgent(npc_in_builder.name, npc_in_builder.url, npc_in_builder.memory)
        npc_entity_in_builder.add(NPCComponent, npc_agent.name, npc_agent, "")
        npc_entity_in_builder.add(SimpleRPGRoleComponent, npc_agent.name, 100, 100, 10, "")
        npc_entity_in_builder.add(BackpackComponent, npc_agent.name)
        context.file_system.init_backpack_component(npc_entity_in_builder.get(BackpackComponent))
        logger.debug(f"创建npc：{npc_agent.name}")
        if len(npc_in_builder.props) > 0:
            for prop in npc_in_builder.props:
                context.file_system.add_content_into_backpack(npc_entity_in_builder.get(BackpackComponent), prop.name)
                logger.debug(f"{npc_agent.name}的背包中有：{prop.name}")
    
    return res
###############################################################################################################################################
def create_stage_entities(context: ExtendedContext, stage_builder: StageBuilder) -> List[Entity]:
    res: List[Entity] = []
    if stage_builder.data is None:
        logger.error("没有StageBuilder数据，请检查World.json配置。")
        return res
    
    # 创建stage相关配置
    for stage in stage_builder.stages:
        stage_agent = ActorAgent(stage.name, stage.url, stage.memory)
        stage_entity = context.create_entity()
        stage_entity.add(StageComponent, stage_agent.name, stage_agent, [])
        stage_entity.add(SimpleRPGRoleComponent, stage_agent.name, 10000, 10000, 1, "")
        logger.debug(f"创建Stage：{stage.name}")

        ## 重新设置npc和stage的关系
        for npc in stage.npcs:
            if isinstance(npc, dict):
                npc_name = npc.get("name", "")
                npc_url = npc.get("url", "")
                npc_memory = npc.get("memory", "")
                npc_agent = ActorAgent(npc_name, npc_url, npc_memory)
                npc_entity_in_builder: Optional[Entity] = context.getnpc(npc_name)
                if npc_entity_in_builder is None:
                    continue
                if npc_entity_in_builder.has(NPCComponent):
                    npc_entity_in_builder.replace(NPCComponent, npc_name, npc_agent, stage_agent.name)
                    logger.debug(f"重新设置npc：{npc_name}的stage为：{stage.name}")

        # 创建道具
        for unique_prop in stage.props:
            prop_entity = context.create_entity()
            if isinstance(unique_prop, dict):
                prop_entity.add(UniquePropComponent, unique_prop.get("name"))
                logger.debug(f'创建道具：{unique_prop.get("name")}')
            else:
                logger.error(f"道具配置错误：{unique_prop}")

        ## 创建入口条件和出口条件
        enter_condition_set = set()
        for enter_condition in stage.entry_conditions:
            enter_condition_set.add(enter_condition.name)
        if len(enter_condition_set) > 0:
            stage_entity.add(StageEntryConditionComponent, enter_condition_set)
            logger.debug(f"{stage_agent.name}的入口条件为：{enter_condition_set}")

        exit_condition_set = set()
        for exit_condition in stage.exit_conditions:
            exit_condition_set.add(exit_condition.name)
        if len(exit_condition_set) > 0:
            stage_entity.add(StageExitConditionComponent, set(exit_condition_set))
            logger.debug(f"{stage_agent.name}的出口条件为：{exit_condition_set}")

    return res
###############################################################################################################################################


def create_entities_by_worlddata(context: ExtendedContext, world_data_builder: WorldDataBuilder) -> None:
    if world_data_builder is None or world_data_builder.data is None:
        logger.error("没有WorldBuilder数据，请检查World.json配置。")
        return
    ##创建Admin npc builder
    # admin_npc_builder: AdminNpcBuilder = world_data_builder.admin_npc_builder
    # if admin_npc_builder.data is None:
    #     logger.error("没有AdminNpcBuilder数据，请检查World.json配置。")
    #     return
    # for admin_npc in admin_npc_builder.npcs:
    #     admin_npc_agent = ActorAgent(admin_npc.name, admin_npc.url, admin_npc.memory)
    #     admin_npc_entity = context.create_entity()
    #     admin_npc_entity.add(WorldComponent, admin_npc_agent.name, admin_npc_agent)
    #     logger.debug(f"创建Admin npc：{admin_npc.name}")

    adminnpcs = create_admin_npc_entities(context, world_data_builder.admin_npc_builder)

    

    # 创建Player npc builder
    # player_npc_builder: PlayerNpcBuilder = world_data_builder.player_npc_builder
    # if player_npc_builder.data is None:
    #     logger.error("没有PlayerNpcBuilder数据，请检查World.json配置。")
    #     return
    # for player_npc in player_npc_builder.npcs:
    #     player_npc_agent = ActorAgent(player_npc.name, player_npc.url, player_npc.memory)
    #     player_npc_entity = context.create_entity()
    #     player_npc_entity.add(PlayerComponent, player_npc.name)
    #     player_npc_entity.add(SimpleRPGRoleComponent, player_npc.name, 10000, 10000, 10, "")
    #     player_npc_entity.add(NPCComponent, player_npc.name, player_npc_agent, "")
    #     player_npc_entity.add(BackpackComponent, player_npc.name)
    #     context.file_system.init_backpack_component(player_npc_entity.get(BackpackComponent))
    #     logger.debug(f"创建Player npc：{player_npc.name}")
    #     if len(player_npc.props) > 0:
    #         for prop in player_npc.props:
    #             context.file_system.add_content_into_backpack(player_npc_entity.get(BackpackComponent), prop.name)
    #             logger.debug(f"{player_npc.name}的背包中有：{prop.name}")

    playernpcs = create_player_npc_entities(context, world_data_builder.player_npc_builder)

    # 创建npc builder
    # npc_builder: NpcBuilder = world_data_builder.npc_buidler
    # if npc_builder.data is None:
    #     logger.error("没有NpcBuilder数据，请检查World.json配置。")
    #     return
    # for npc_in_builder in npc_builder.npcs:
    #     npc_entity_in_builder = context.create_entity()
    #     npc_agent = ActorAgent(npc_in_builder.name, npc_in_builder.url, npc_in_builder.memory)
    #     npc_entity_in_builder.add(NPCComponent, npc_agent.name, npc_agent, "")
    #     npc_entity_in_builder.add(SimpleRPGRoleComponent, npc_agent.name, 100, 100, 10, "")
    #     npc_entity_in_builder.add(BackpackComponent, npc_agent.name)
    #     context.file_system.init_backpack_component(npc_entity_in_builder.get(BackpackComponent))
    #     logger.debug(f"创建npc：{npc_agent.name}")
    #     if len(npc_in_builder.props) > 0:
    #         for prop in npc_in_builder.props:
    #             context.file_system.add_content_into_backpack(npc_entity_in_builder.get(BackpackComponent), prop.name)
    #             logger.debug(f"{npc_agent.name}的背包中有：{prop.name}")
    
    npcs = create_npc_entities(context, world_data_builder.npc_buidler)


    ##创建stage builder，并重新设置关系
    # stage_builder: StageBuilder = world_data_builder.stage_builder
    # if stage_builder.data is None:
    #     logger.error("没有StageBuilder数据，请检查World.json配置。")
    #     return
    # # 创建stage相关配置
    # for stage in stage_builder.stages:
    #     stage_agent = ActorAgent(stage.name, stage.url, stage.memory)
    #     stage_entity = context.create_entity()
    #     stage_entity.add(StageComponent, stage_agent.name, stage_agent, [])
    #     stage_entity.add(SimpleRPGRoleComponent, stage_agent.name, 10000, 10000, 1, "")
    #     logger.debug(f"创建Stage：{stage.name}")
    #     ## 重新设置npc和stage的关系
    #     for npc in stage.npcs:
    #         if isinstance(npc, dict):
    #             npc_name = npc.get("name", "")
    #             npc_url = npc.get("url", "")
    #             npc_memory = npc.get("memory", "")
    #             npc_agent = ActorAgent(npc_name, npc_url, npc_memory)
    #             npc_entity_in_builder: Optional[Entity] = context.getnpc(npc_name)
    #             if npc_entity_in_builder.has(NPCComponent):
    #                 npc_entity_in_builder.replace(NPCComponent, npc_name, npc_agent, stage_agent.name)
    #                 logger.debug(f"重新设置npc：{npc_name}的stage为：{stage.name}")

    #     # 创建道具
    #     for unique_prop in stage.props:
    #         prop_entity = context.create_entity()
    #         if isinstance(unique_prop, dict):
    #             prop_entity.add(UniquePropComponent, unique_prop.get("name"))
    #             logger.debug(f'创建道具：{unique_prop.get("name")}')
    #         else:
    #             logger.error(f"道具配置错误：{unique_prop}")

    #     ## 创建入口条件和出口条件
    #     enter_condition_set = set()
    #     for enter_condition in stage.entry_conditions:
    #         enter_condition_set.add(enter_condition.name)
    #     if len(enter_condition_set) > 0:
    #         stage_entity.add(StageEntryConditionComponent, enter_condition_set)
    #         logger.debug(f"{stage_agent.name}的入口条件为：{enter_condition_set}")

    #     exit_condition_set = set()
    #     for exit_condition in stage.exit_conditions:
    #         exit_condition_set.add(exit_condition.name)
    #     if len(exit_condition_set) > 0:
    #         stage_entity.add(StageExitConditionComponent, set(exit_condition_set))
    #         logger.debug(f"{stage_agent.name}的出口条件为：{exit_condition_set}")

    stages = create_stage_entities(context, world_data_builder.stage_builder)

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
def main() -> None:

    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.add(f"logs/{log_start_time}.log", level="DEBUG")

    context = ExtendedContext()
    processors = Processors()
    playername = "yanghang"

    world_name = input("请输入要进入的世界名称(必须与自动化创建的名字一致):")
    # 检查是否有存档
    save_folder = f"./budding_world/saved_runtimes/{world_name}.json"
    if not os.path.exists(save_folder):
        world_data_path: str = f"./budding_world/gen_runtimes/{world_name}.json"
    else:
        world_data_path = save_folder

    world_data_builder: Optional[WorldDataBuilder] = WorldDataBuilder()
    if world_data_builder is None:
        logger.error("WorldDataBuilder初始化失败。")
        return
    if world_data_builder.check_version_valid(world_data_path):
        world_data_builder.build()
    else:
        logger.error("World.json版本不匹配，请检查版本号。")
        return

    create_entities_by_worlddata(context, world_data_builder)   

    #初始化系统########################
    processors.add(InitSystem(context))
    #规划逻辑########################
    processors.add(StagePlanSystem(context))
    processors.add(NPCPlanSystem(context))
    #行动逻辑########################
    processors.add(TagActionSystem(context))
    processors.add(MindVoiceActionSystem(context))
    processors.add(WhisperActionSystem(context))
    processors.add(BroadcastActionSystem(context))
    processors.add(SpeakActionSystem(context))
    #死亡必须是战斗之后，因为如果死了就不能离开###############
    processors.add(FightActionSystem(context))
    processors.add(DeadActionSystem(context)) 
    #########################################
    # 处理搜寻道具行为
    processors.add(SearchPropsSystem(context))
    # 处理离开并去往的行为
    processors.add(LeaveForActionSystem(context))
    #行动结束后导演
    processors.add(DirectorSystem(context))
    #########################################
    ###必须最后
    processors.add(DestroySystem(context))
    processors.add(DataSaveSystem(context))

    ####
    inited:bool = False
    started:bool = False

    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            break

        elif "/run" in usr_input:
            #顺序不要动！！！！！！！！！
            if not inited:
                inited = True
                processors.activate_reactive_processors()
                processors.initialize()
            processors.execute()
            processors.cleanup()
            started = True
            logger.debug("==============================================")

        elif "/push" in usr_input:
            # if not started:
            #     logger.warning("请先/run")
            #     continue
            command = "/push"
            input_content = parse_command(usr_input, command) 
            push_command_parse_res: tuple[str, str] = parse_target_and_message_by_symbol(input_content)
            logger.debug(f"</force push command to {push_command_parse_res[0]}>:", input_content)
            debug_push(context, push_command_parse_res[0], push_command_parse_res[1])
            logger.debug(f"{'=' * 50}")

        elif "/ask" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/ask"
            input_content = parse_command(usr_input, command)
            ask_command_parse_res: tuple[str, str] = parse_target_and_message_by_symbol(input_content)
            logger.debug(f"</ask command to {ask_command_parse_res[0]}>:", input_content)
            debug_ask(context, ask_command_parse_res[0], ask_command_parse_res[1])
            logger.debug(f"{'=' * 50}")

        elif "/showstages" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/showstages"
            who = parse_command(usr_input, command)
            log = context.show_stages_log()
            logger.debug(f"/showstages: \n{log}")
            logger.debug(f"{'=' * 50}")

        elif "/who" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/who"
            who = parse_command(usr_input, command)
            debug_be_who(context, who, playername)
            logger.debug(f"{'=' * 50}")
           
        elif "/attack" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/attack"
            target_name = parse_command(usr_input, command)    
            debug_attack(context, target_name)
            logger.debug(f"{'=' * 50}")
        
        elif "/mem" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/mem"
            target_name = parse_command(usr_input, command)
            debug_chat_history(context, target_name)
            logger.debug(f"{'=' * 50}")
        
        elif "/leave" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/leave"
            target_name = parse_command(usr_input, command)
            debug_leave(context, target_name)
            logger.debug(f"{'=' * 50}")
        
        elif "/broadcast" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/broadcast"
            content = parse_command(usr_input, command)
            debug_broadcast(context, content)
            logger.debug(f"{'=' * 50}")
            
        elif "/speak" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/speak"
            content = parse_command(usr_input, command)
            debug_speak(context, content)
            logger.debug(f"{'=' * 50}")

        elif "/whisper" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/whisper"
            content = parse_command(usr_input, command)
            debug_whisper(context, content)
            logger.debug(f"{'=' * 50}")
        
        elif "/search" in usr_input:
            if not started:
                logger.warning("请先/run")
                continue
            command = "/search"
            content = parse_command(usr_input, command)
            debug_search(context, content)
            logger.debug(f"{'=' * 50}")

    processors.clear_reactive_processors()
    processors.tear_down()
    logger.info("Game Over")

###############################################################################################################################################
def debug_push(context: ExtendedContext, name: str, content: str) -> Union[None, NPCComponent, StageComponent, WorldComponent]:

    npc_entity: Optional[Entity] = context.getnpc(name)
    if npc_entity is not None:
        npc_comp: NPCComponent = npc_entity.get(NPCComponent)
        npc_request: Optional[str] = npc_comp.agent.request(content)
        if npc_request is not None:
            npc_comp.agent.chat_history.pop()
        return npc_comp
    
    stage_entity: Optional[Entity] = context.getstage(name)
    if stage_entity is not None:
        stage_comp: StageComponent = stage_entity.get(StageComponent)
        stage_request: Optional[str] = stage_comp.agent.request(content)
        if stage_request is not None:
            stage_comp.agent.chat_history.pop()
        return stage_comp
    
    world_entity: Optional[Entity] = context.getworld()
    if world_entity is not None:
        world_comp: WorldComponent = world_entity.get(WorldComponent)
        request: Optional[str] = world_comp.agent.request(content)
        if request is not None:
            world_comp.agent.chat_history.pop()
        return world_comp

    return None        
    
def debug_ask(context: ExtendedContext, name: str, content: str) -> None:
    pushed_comp = debug_push(context, name, content)
    if pushed_comp is None:
        logger.warning(f"debug_ask: {name} not found.")
        return
    pushed_agent: ActorAgent = pushed_comp.agent
    pushed_agent.chat_history.pop()

###############################################################################################################################################
def debug_be_who(context: ExtendedContext, name: str, playname: str) -> None:

    playerentity = context.getplayer()
    if playerentity is not None:
        playercomp = playerentity.get(PlayerComponent)
        logger.debug(f"debug_be_who current player is : {playercomp.name}")
        playerentity.remove(PlayerComponent)

    entity = context.getnpc(name)
    if entity is not None:
        npccomp = entity.get(NPCComponent)
        logger.debug(f"debug_be_who => : {npccomp.name} is {playname}")
        entity.add(PlayerComponent, playname)
        return
    
    entity = context.getstage(name)
    if entity is not None:
        stagecomp = entity.get(StageComponent)
        logger.debug(f"debug_be_who => : {stagecomp.name} is {playname}")
        entity.add(PlayerComponent, playname)
        return
###############################################################################################################################################
def debug_attack(context: ExtendedContext, dest: str) -> None:
    
    playerentity = context.getplayer()
    if playerentity is None:
        logger.warning("debug_attack: player is None")
        return
       
    if playerentity.has(NPCComponent):
        npc_comp: NPCComponent = playerentity.get(NPCComponent)
        action = ActorAction(npc_comp.name, "FightActionComponent", [dest])
        playerentity.add(FightActionComponent, action)
        if not playerentity.has(HumanInterferenceComponent):
            playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}攻击{dest}')
        logger.debug(f"debug_attack: {npc_comp.name} add {action}")
        return
    
    elif playerentity.has(StageComponent):
        stage_comp: StageComponent = playerentity.get(StageComponent)
        action = ActorAction(stage_comp.name, "FightActionComponent", [dest])
        if not playerentity.has(HumanInterferenceComponent):
            playerentity.add(HumanInterferenceComponent, f'{stage_comp.name}攻击{dest}')
        playerentity.add(FightActionComponent, action)
        logger.debug(f"debug_attack: {stage_comp.name} add {action}")
        return

###############################################################################################################################################
    
def debug_chat_history(context: ExtendedContext, name: str) -> None:
    entity = context.getnpc(name)
    if entity is not None:
        npc_comp: NPCComponent = entity.get(NPCComponent)
        npc_agent: ActorAgent = npc_comp.agent
        logger.info(f"{'=' * 50}\ndebug_chat_history for {npc_comp.name} => :")
        for history in npc_agent.chat_history:
            if isinstance(history, HumanMessage):
                logger.info(f"{'=' * 50}\nHuman:{history.content}")
            elif isinstance(history, AIMessage):
                logger.info(f"{'=' * 50}\nAI:{history.content}")
        logger.info(f"{'=' * 50}")
        return
    
    entity = context.getstage(name)
    if entity is not None:
        stage_comp: StageComponent = entity.get(StageComponent)
        stage_agent: ActorAgent = stage_comp.agent
        logger.info(f"{'=' * 50}\ndebug_chat_history for {stage_comp.name} => :\n")
        for history in stage_agent.chat_history:
            if isinstance(history, HumanMessage):
                logger.info(f"Human:{history.content}")
            elif isinstance(history, AIMessage):
                logger.info(f"AI:{history.content}")
        logger.info(f"{'=' * 50}")
        return
    
    entity = context.getworld()
    if entity is not None:
        world_comp: WorldComponent = entity.get(WorldComponent)
        world_agent: ActorAgent = world_comp.agent
        logger.info(f"{'=' * 50}\ndebug_chat_history for {world_comp.name} => :\n")
        for history in world_agent.chat_history:
            if isinstance(history, HumanMessage):
                logger.info(f"Human:{history.content}")
            elif isinstance(history, AIMessage):
                logger.info(f"AI:{history.content}")
        logger.info(f"{'=' * 50}")
        return


###############################################################################################################################################

def debug_leave(context: ExtendedContext, stagename: str) -> None:
    playerentity = context.getplayer()
    if playerentity is None:
        logger.warning("debug_leave: player is None")
        return
    
    npc_comp: NPCComponent = playerentity.get(NPCComponent)
    action = ActorAction(npc_comp.name, "LeaveForActionComponent", [stagename])
    playerentity.add(LeaveForActionComponent, action)
    if not playerentity.has(HumanInterferenceComponent):
        playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}离开了{stagename}')

    newmemory = f"""{{
        "LeaveForActionComponent": ["{stagename}"]
    }}"""
    context.add_agent_memory(playerentity, newmemory)
    logger.debug(f"debug_leave: {npc_comp.name} add {action}")
    
###############################################################################################################################################
def debug_broadcast(context: ExtendedContext, content: str) -> None:
    playerentity = context.getplayer()
    if playerentity is None:
        logger.warning("debug_broadcast: player is None")
        return
    
    npc_comp: NPCComponent = playerentity.get(NPCComponent)
    action = ActorAction(npc_comp.name, "BroadcastActionComponent", [content])
    playerentity.add(BroadcastActionComponent, action)
    playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}大声说道：{content}')

    newmemory = f"""{{
        "BroadcastActionComponent": ["{content}"]
    }}"""
    context.add_agent_memory(playerentity, newmemory)
    logger.debug(f"debug_broadcast: {npc_comp.name} add {action}")

###############################################################################################################################################
def debug_speak(context: ExtendedContext, content: str) -> None:
    playerentity = context.getplayer()
    if playerentity is None:
        logger.warning("debug_speak: player is None")
        return
    
    npc_comp: NPCComponent = playerentity.get(NPCComponent)
    action = ActorAction(npc_comp.name, "SpeakActionComponent", [content])
    playerentity.add(SpeakActionComponent, action)
    if not playerentity.has(HumanInterferenceComponent):
        playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}说道：{content}')

    newmemory = f"""{{
        "SpeakActionComponent": ["{content}"]
    }}"""
    context.add_agent_memory(playerentity, newmemory)
    logger.debug(f"debug_speak: {npc_comp.name} add {action}")

###############################################################################################################################################
def debug_whisper(context: ExtendedContext, content: str) -> None:
    playerentity = context.getplayer()
    if playerentity is None:
        logger.warning("debug_whisper: player is None")
        return
    
    npc_comp: NPCComponent = playerentity.get(NPCComponent)
    action = ActorAction(npc_comp.name, "WhisperActionComponent", [content])
    playerentity.add(WhisperActionComponent, action)
    if not playerentity.has(HumanInterferenceComponent):
        playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}低语道：{content}')

    newmemory = f"""{{
        "WhisperActionComponent": ["{content}"]
    }}"""
    context.add_agent_memory(playerentity, newmemory)
    logger.debug(f"debug_whisper: {npc_comp.name} add {action}")

###############################################################################################################################################

def debug_search(context: ExtendedContext, content: str) -> None:
    playerentity = context.getplayer()
    if playerentity is None:
        logger.warning("debug_search: player is None")
        return
    
    npc_comp: NPCComponent = playerentity.get(NPCComponent)
    action = ActorAction(npc_comp.name, "SearchActionComponent", [content])
    playerentity.add(SearchActionComponent, action)
    if not playerentity.has(HumanInterferenceComponent):
        playerentity.add(HumanInterferenceComponent, f'{npc_comp.name}搜索{content}')

    newmemory = f"""{{
        "SearchActionComponent": ["{content}"]
    }}"""
    context.add_agent_memory(playerentity, newmemory)
    logger.debug(f"debug_search: {npc_comp.name} add {action}")


if __name__ == "__main__":
    main()