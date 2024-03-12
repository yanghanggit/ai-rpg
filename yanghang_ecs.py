
from entitas import Context, Processors
import json
from builder import WorldBuilder
from console import Console
from components import WorldComponent, StageComponent, NPCComponent, FightActionComponent, PlayerComponent
from actor_action import ActorAction
from actor_agent import ActorAgent
from init_system import InitSystem
from stage_plan_system import StagePlanSystem
from npc_plan_system import NPCPlanSystem
from speak_action_system import SpeakActionSystem
from fight_action_system import FightActionSystem
from leave_action_system import LeaveActionSystem
from director_system import DirectorSystem
from extended_context import ExtendedContext
from dead_action_system import DeadActionSystem
from destroy_system import DestroySystem


###############################################################################################################################################
def create_entities(context: Context, worldbuilder: WorldBuilder) -> None:
        ##创建world
        worldagent = ActorAgent()
        worldagent.init(worldbuilder.data['name'], worldbuilder.data['url'])
        world_entity = context.create_entity() 
        world_entity.add(WorldComponent, worldagent.name, worldagent)

        for stage_builder in worldbuilder.stage_builders:     
            #
            if stage_builder.data['name'] == '悠扬林谷':
                return
            #创建stage       
            stage_agent = ActorAgent()
            stage_agent.init(stage_builder.data['name'], stage_builder.data['url'])
            stage_entity = context.create_entity()
            stage_entity.add(StageComponent, stage_agent.name, stage_agent, [])
            
            for npc_builder in stage_builder.npc_builders:
                #创建npc
                npc_agent = ActorAgent()
                npc_agent.init(npc_builder.data['name'], npc_builder.data['url'])
                npc_entity = context.create_entity()
                npc_entity.add(NPCComponent, npc_agent.name, npc_agent, stage_agent.name)

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
def main() -> None:

    context = ExtendedContext()
    processors = Processors()
    console = Console("测试后台管理")
    path: str = "./yanghang_stage1.json"

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

    print("<<<<<<<<<<<<<<<<<<<<< 构建系统 >>>>>>>>>>>>>>>>>>>>>>>>>>>")
    #初始化系统
    processors.add(InitSystem(context))
    
    #规划逻辑
    processors.add(StagePlanSystem(context))
    processors.add(NPCPlanSystem(context))

    #行动逻辑
    processors.add(SpeakActionSystem(context))
    processors.add(FightActionSystem(context))
    processors.add(LeaveActionSystem(context))
    processors.add(DeadActionSystem(context))

    #行动结束后导演
    processors.add(DirectorSystem(context))

    ###必须最后
    processors.add(DestroySystem(context))


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

        elif "/who" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/who"
            who = console.parse_command(usr_input, command)
            debug_be_who(context, who)
           

        elif "/attack" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/attack"
            target_name = console.parse_command(usr_input, command)    
            debug_attack(context, target_name)
            #print("==============================================")   

    processors.clear_reactive_processors()
    processors.tear_down()
    print("end.")
###############################################################################################################################################
def debug_be_who(context: ExtendedContext, name: str) -> None:

    playerentity = context.getplayer()
    if playerentity is not None:
        comp = playerentity.get(PlayerComponent)
        print(f"debug_be_who current is : {comp.name}")
        playerentity.remove(PlayerComponent)

    entity = context.getnpc(name)
    if entity is not None:
        comp = entity.get(NPCComponent)
        print(f"debug_be_who => : {name} is {comp.name}")
        entity.add(PlayerComponent, comp.name)
        return
    
    entity = context.getstage(name)
    if entity is not None:
        comp = entity.get(StageComponent)
        print(f"debug_be_who => : {name} is {comp.name}")
        entity.add(PlayerComponent, comp.name)
        return

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
def debug_attack(context: ExtendedContext, dest: str) -> None:
    playerentity = context.getplayer()
    if playerentity is not None:
        comp = playerentity.get(PlayerComponent)
        action = ActorAction()
        action.init(comp.name, "FightActionComponent", [dest])
        playerentity.add(FightActionComponent, action)
        print(f"debug_attack: {comp.name} add {action}")
        return

###############################################################################################################################################
    
if __name__ == "__main__":
    main()