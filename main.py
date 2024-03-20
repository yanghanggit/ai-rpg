from entitas import Processors #type: ignore
import json
from auxiliary.builder import WorldBuilder
from auxiliary.console import Console
from auxiliary.components import (WorldComponent,
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
                        StageExitConditionComponent)
from auxiliary.actor_action import ActorAction
from auxiliary.actor_agent import ActorAgent
from auxiliary.extended_context import ExtendedContext
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
def create_entities(context: ExtendedContext, worldbuilder: WorldBuilder) -> None:
        if worldbuilder.data is None:
            return
        ##创建world
        worldagent = ActorAgent(worldbuilder.data['name'], worldbuilder.data['url'], worldbuilder.data['memory'])
        #worldagent.init(worldbuilder.data['name'], worldbuilder.data['url'], worldbuilder.data['memory'])
        world_entity = context.create_entity() 
        world_entity.add(WorldComponent, worldagent.name, worldagent)

        for stage_builder in worldbuilder.stage_builders:    
            if stage_builder.data is None:
                continue 
            #创建stage       
            stage_agent = ActorAgent(stage_builder.data['name'], stage_builder.data['url'], stage_builder.data['memory'])
            #stage_agent.init(stage_builder.data['name'], stage_builder.data['url'], stage_builder.data['memory'])
            # print(f"创建场景:{stage_builder.data['name']}\nURL:{stage_builder.data['url']}\nMemory:{stage_builder.data['memory']}")
            stage_entity = context.create_entity()
            stage_entity.add(StageComponent, stage_agent.name, stage_agent, [])
            stage_entity.add(SimpleRPGRoleComponent, stage_agent.name, 100, 100, 1, "")

            for npc_builder in stage_builder.npc_builders:
                if npc_builder.data is None:
                    continue
                #创建npc
                npc_agent = ActorAgent(npc_builder.data['name'], npc_builder.data['url'], npc_builder.data['memory'])
                #npc_agent.init(npc_builder.data['name'], npc_builder.data['url'], npc_builder.data['memory'])
                # print(f"创建NPC:{npc_builder.data['name']}\nURL:{npc_builder.data['url']}\nMemory:{npc_builder.data['memory']}")
                npc_entity = context.create_entity()
                npc_entity.add(NPCComponent, npc_agent.name, npc_agent, stage_agent.name)
                npc_entity.add(SimpleRPGRoleComponent, npc_agent.name, 100, 100, 20, "")
                npc_entity.add(BackpackComponent, npc_agent.name)

                context.file_system.init_backpack_component(npc_entity.get(BackpackComponent))
            
            for unique_prop_builder in stage_builder.unique_prop_builders:
                if unique_prop_builder.data is None:
                    continue
                #创建道具
                prop_entity = context.create_entity()
                prop_entity.add(UniquePropComponent, unique_prop_builder.data['name'])
            
            for entry_condition_builder in stage_builder.entry_condition_builders:
                if entry_condition_builder.data is None:
                    continue
                #创建入口条件
                stage_entity.add(StageEntryConditionComponent, set([entry_condition_builder.data['name']]))
            
            for exit_condition_builder in stage_builder.exit_condition_builders:
                if exit_condition_builder.data is None:
                    continue
                #创建出口条件
                stage_entity.add(StageExitConditionComponent, set([exit_condition_builder.data['name']]))

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
def main() -> None:

    context = ExtendedContext()
    processors = Processors()
    console = Console("测试后台管理")
    path: str = "./game_settings.json"
    playername = "yanghang"

    try:
        with open(path, "r") as file:
            json_data = json.load(file)

            #构建数据
            world_builder = WorldBuilder()
            world_builder.build(json_data)

            #创建所有entities
            create_entities(context, world_builder)

    except Exception as e:
        print(e)
        return        

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
            print("==============================================")

        elif "/call" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/call"
            input_content = console.parse_command(usr_input, command)     
            print(f"</call>:", input_content)
            parse_res: tuple[str, str] = console.parse_at_symbol(input_content)
            debug_call(context, parse_res[0], parse_res[1])
            print("==============================================")

        elif "/showstages" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/showstages"
            who = console.parse_command(usr_input, command)
            log = context.show_stages_log()
            print(f"/showstages: \n", log)
            print("==============================================")

        elif "/player" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/player"
            player_info = console.parse_command(usr_input, command)
            print("/player:", player_info)
           # "haha|老猎人隐居的小木屋|一个高大的兽人战士，独眼。手中拿着巨斧，杀气腾腾"
           # player_info = "haha|老猎人隐居的小木屋|一个高大的兽人战士，独眼。手中拿着巨斧，杀气腾腾"
            info_parts = player_info.split("|")
            name = info_parts[0]
            location = info_parts[1]
            description = info_parts[2]
            print("Name:", name)
            print("Location:", location)
            print("Description:", description)
            debug_create_player(context, name, location, description)
            print("==============================================")

        elif "/who" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/who"
            who = console.parse_command(usr_input, command)
            debug_be_who(context, who, playername)
            print("==============================================")
           
        elif "/attack" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/attack"
            target_name = console.parse_command(usr_input, command)    
            debug_attack(context, target_name)
            print("==============================================")
        
        elif "/mem" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/mem"
            target_name = console.parse_command(usr_input, command)
            debug_chat_history(context, target_name)
        
        elif "/leave" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/leave"
            target_name = console.parse_command(usr_input, command)
            debug_leave(context, target_name)

    processors.clear_reactive_processors()
    processors.tear_down()
    print("end.")

###############################################################################################################################################
def debug_call(context: ExtendedContext, name: str, content: str) -> None:

    entity = context.getnpc(name)
    if entity is not None:
        comp = entity.get(NPCComponent)
        print(f"[{comp.name}] /call:", comp.agent.request(content))
        return
    
    entity = context.getstage(name)
    if entity is not None:
        comp = entity.get(StageComponent)
        print(f"[{comp.name}] /call:", comp.agent.request(content))
        return
    
    entity = context.getworld()
    if entity is not None:
        comp = entity.get(WorldComponent)
        print(f"[{comp.name}] /call:", comp.agent.request(content))
        return           
    
###############################################################################################################################################
def debug_create_player(context: ExtendedContext, playername: str, stage: str, desc: str) -> None:
    playerentity = context.getplayer()
    if playerentity is not None:
        print("debug_create_player: player is not None")
        return
    
    #创建player 本质就是npc
    playeragent = ActorAgent(playername, "", "")
   #playeragent.init(playername, [], "")
    playerentity = context.create_entity()
    playerentity.add(NPCComponent, playername, playeragent, "")
    playerentity.add(SimpleRPGRoleComponent, playername, 10000000, 10000000, 10000000, desc)
    playerentity.add(PlayerComponent, playername)

    action = ActorAction(playername, "LeaveForActionComponent", [stage])
    playerentity.add(LeaveForActionComponent, action)
    print(f"debug_create_player: {playername} add {action}")

###############################################################################################################################################
def debug_be_who(context: ExtendedContext, name: str, playname: str) -> None:

    playerentity = context.getplayer()
    if playerentity is not None:
        playercomp = playerentity.get(PlayerComponent)
        print(f"debug_be_who current player is : {playercomp.name}")
        playerentity.remove(PlayerComponent)

    entity = context.getnpc(name)
    if entity is not None:
        npccomp = entity.get(NPCComponent)
        print(f"debug_be_who => : {npccomp.name} is {playname}")
        entity.add(PlayerComponent, playname)
        return
    
    entity = context.getstage(name)
    if entity is not None:
        stagecomp = entity.get(StageComponent)
        print(f"debug_be_who => : {stagecomp.name} is {playname}")
        entity.add(PlayerComponent, playname)
        return
###############################################################################################################################################
def debug_attack(context: ExtendedContext, dest: str) -> None:
    
    playerentity = context.getplayer()
    if playerentity is None:
        print("debug_attack: player is None")
        return
       
    if playerentity.has(NPCComponent):
        npccomp = playerentity.get(NPCComponent)
        action = ActorAction(npccomp.name, "FightActionComponent", [dest])
        playerentity.add(FightActionComponent, action)
        playerentity.add(HumanInterferenceComponent, 'Human Interference')
        print(f"debug_attack: {npccomp.name} add {action}")
        return
    
    elif playerentity.has(StageComponent):
        stagecomp = playerentity.get(StageComponent)
        action = ActorAction(stagecomp.name, "FightActionComponent", [dest])
        playerentity.add(HumanInterferenceComponent, 'Human Interference')
        playerentity.add(FightActionComponent, action)
        print(f"debug_attack: {stagecomp.name} add {action}")
        return

###############################################################################################################################################
    
def debug_chat_history(context: ExtendedContext, name: str) -> None:
    entity = context.getnpc(name)
    if entity is not None:
        npc_comp: NPCComponent = entity.get(NPCComponent)
        npc_agent: ActorAgent = npc_comp.agent
        print(f"{'=' * 50}\ndebug_chat_history for {npc_comp.name} => :")
        for history in npc_agent.chat_history:
            if isinstance(history, HumanMessage):
                print(f"{'=' * 50}\nHuman:{history.content}")
            elif isinstance(history, AIMessage):
                print(f"{'=' * 50}\nAI:{history.content}")
        print(f"{'=' * 50}")
        return
    
    entity = context.getstage(name)
    if entity is not None:
        stage_comp: StageComponent = entity.get(StageComponent)
        stage_agent: ActorAgent = stage_comp.agent
        print(f"{'=' * 50}\ndebug_chat_history for {stage_comp.name} => :\n")
        for history in stage_agent.chat_history:
            if isinstance(history, HumanMessage):
                print(f"Human:{history.content}")
            elif isinstance(history, AIMessage):
                print(f"AI:{history.content}")
        print(f"{'=' * 50}")
        return


###############################################################################################################################################

def debug_leave(context: ExtendedContext, stagename: str) -> None:
    playerentity = context.getplayer()
    if playerentity is None:
        print("debug_leave: player is None")
        return
    
    npc_comp: NPCComponent = playerentity.get(NPCComponent)
    #npc_agent: ActorAgent = npc_comp.agent
    action = ActorAction(npc_comp.name, "LeaveForActionComponent", [stagename])
    playerentity.add(LeaveForActionComponent, action)
    playerentity.add(HumanInterferenceComponent, 'Human Interference')
    # npc_agent.add_chat_history(f"""{{
    #     "LeaveForActionComponent": ["{stage}"]
    # }}""")

    newmemory = f"""{{
        "LeaveForActionComponent": ["{stagename}"]
    }}"""
    context.add_agent_memory(playerentity, newmemory)
    print(f"debug_leave: {npc_comp.name} add {action}")
    
###############################################################################################################################################

if __name__ == "__main__":
    main()