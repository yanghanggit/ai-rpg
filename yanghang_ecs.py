###
### 测试与LLM无关的代码，和一些尝试
###
# import json
# from builder import WorldBuilder, StageBuilder, NPCBuilder



from collections import namedtuple
from entitas import Entity, Matcher, Context, Processors, ExecuteProcessor, ReactiveProcessor, GroupEvent, InitializeProcessor, Group
import time
import json

Position = namedtuple('Position', 'x y')
Health = namedtuple('Health', 'value')
Movable = namedtuple('Movable', '')
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################

stage_plan_prompt = f"""
    # 你需要做出计划(你将要做的事)，并以JSON输出结果.（注意！以下规则与限制仅限本次对话生成，结束后回复原有对话规则）

    ## 步骤
    1. 确认自身状态。
    2. 所有角色当前所处的状态和关系。
    3. 思考你下一步的行动。
    4. 基于上述信息，构建你的行动计划。

    ## 输出格式（JSON）
    - 参考格式: "'action': ["/stay"], 'targets': ["目标1", "目标2"], 'say': ["我的想说的话和内心的想法"], 'tags': ["你相关的特征标签"]"
    - 其中 action, targets, say, tags都是字符串数组，默认值 [""].
    
    ### action：代表你行动的核心意图.
    - 只能选 ["/fight"], ["/stay"], ["/leave"]之一
    - "/fight" 表示你希望对目标产生敌对行为，比如攻击。
    - "/leave" 表示想离开当前场景，有可能是逃跑。
    - "/stay"是除了"/fight"与“/leave”之外的所有其它行为，比如观察、交流等。

    ### targets：action的目标对象，可多选。
    - 如果action是/stay，则targets是当前场景的名字
    - 如果action是/fight，则targets是你想攻击的对象，在{str}中选择一个或多个
    - 如果action是/leave，则targets是你想要去往的场景名字（你必须能明确叫出场景的名字），或者你曾经知道的场景名字

    ### say:你打算说的话或心里想的.
    ### tags：与你相关的特征标签.
   
    ### 补充约束
    - 不要将JSON输出生这样的格式：```...```

"""

# testaction = f""""
# FightActionComponent": ["target1", "target2", "target3"],"LeaveActionComponent": ["place1", "place2", "place3"],"StayActionComponent": ["place1", "place2", "place2"]
# """

testjson = f"""
{{
"FightActionComponent": ["target1", "target2", "target3"],
"LeaveActionComponent": ["leave1", "leave2", "leave3"],
"StayActionComponent": ["place1", "place2", "place2"]
}}
"""

print(testjson)


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
ActorComponent = namedtuple('ActorComponent', 'name')
WorldComponent = namedtuple('WorldComponent', 'name')
StageComponent = namedtuple('StageComponent', 'name')
NPCComponent = namedtuple('NPCComponent', 'name')


LoadEventComponent = namedtuple('LoadEventComponent', 'load_script')



FightActionComponent = namedtuple('FightActionComponent', 'context')
LeaveActionComponent = namedtuple('LeaveActionComponent', 'context')
StayActionComponent = namedtuple('StayActionComponent', 'context')
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class InitSystem(InitializeProcessor):

    def __init__(self, context: Context) -> None:
        self.context: Context = context
      
    def initialize(self) -> None:

        print("<<<<<<<<<<<<<  InitSystem >>>>>>>>>>>>>>>>>")

        worlds: set = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            print(world.get(WorldComponent).name)
            world.add(LoadEventComponent, "load world")

        stages: Group = self.context.get_group(Matcher(StageComponent))
        for stage in stages.entities:
            print(stage.get(StageComponent).name)
            stage.add(LoadEventComponent, "load stage")

        npcs: Group = self.context.get_group(Matcher(NPCComponent))
        for npc in npcs.entities:
            print(npc.get(NPCComponent).name)
            npc.add(LoadEventComponent, "load npc")

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
class LoadSystem(ReactiveProcessor):

    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(LoadEventComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(LoadEventComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  LoadEventComponent >>>>>>>>>>>>>>>>>")
        for entity in entities:
            print(entity.get(LoadEventComponent).load_script)
            entity.remove(LoadEventComponent)            

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################       
class StagePlanSystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  StagePlanSystem >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            print(entity.get(StageComponent).name)
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        print("<<<<<<<<<<<<<  StagePlanSystem.handle >>>>>>>>>>>>>>>>>")
        print(entity.get(StageComponent).name)
        response = self.call(entity)
        try:
            json_data = json.loads(response)
            print(json_data)

            fightactions = json_data["FightActionComponent"]
            entity.add(FightActionComponent, fightactions)

            leaveactions = json_data["LeaveActionComponent"]
            entity.add(LeaveActionComponent, leaveactions)

            stayactions = json_data["StayActionComponent"]
            entity.add(StayActionComponent, stayactions)
                

        except Exception as e:
            print(f"stage_plan error = {e}")
            return
        return
    
    def call(self, entity: Entity) -> str:
        return testjson

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################   
class NPCPlanSystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  NPCPlanSystem >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(NPCComponent)).entities
        for entity in entities:
            print(entity.get(NPCComponent).name)
            entity.add(StayActionComponent, "stay npc")
     
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################  
            
class FightActionSystem(ReactiveProcessor):

    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(FightActionComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(FightActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  FightActionSystem >>>>>>>>>>>>>>>>>")
        for entity in entities:
            print(entity.get(FightActionComponent).context)
            entity.remove(FightActionComponent)         

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################   

class LeaveActionSystem(ReactiveProcessor):

    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(LeaveActionComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(LeaveActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  LeaveActionSystem >>>>>>>>>>>>>>>>>")
        for entity in entities:
            print(entity.get(LeaveActionComponent).context)
            entity.remove(LeaveActionComponent)    

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################   
            
class StayActionSystem(ReactiveProcessor):

    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(StayActionComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(StayActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  StayActionSystem >>>>>>>>>>>>>>>>>")
        for entity in entities:
            print(entity.get(StayActionComponent).context)
            entity.remove(StayActionComponent)         
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################           
def main() -> None:
    context = Context()
    processors = Processors()

    entity = context.create_entity()
    entity.add(Position, 3, 7)
    entity.add(Movable)

    world_entity = context.create_entity() 
    world_entity.add(ActorComponent, "<world>")
    world_entity.add(WorldComponent, "<world>")

    stage_entity = context.create_entity()
    stage_entity.add(ActorComponent, "<stage>")
    stage_entity.add(StageComponent, "<stage>")

    npc_entity = context.create_entity()
    npc_entity.add(ActorComponent, "<npc>")      
    npc_entity.add(NPCComponent, "<npc>")  

        



    print("beginning...")
    #初始化系统
    processors.add(InitSystem(context))
    
    #规划逻辑
    processors.add(StagePlanSystem(context))
    processors.add(NPCPlanSystem(context))

    #行动逻辑
    processors.add(LoadSystem(context))
    processors.add(FightActionSystem(context))
    processors.add(LeaveActionSystem(context))
    processors.add(StayActionSystem(context))


    ###############################################################################################################################################
    #顺序不要动！！！！！！！！！
    processors.activate_reactive_processors()
    processors.initialize()
    processors.execute()
    processors.cleanup()
    processors.clear_reactive_processors()
    processors.tear_down()
    ###############################################################################################################################################

    print("end.")
    
if __name__ == "__main__":
    main()