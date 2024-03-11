
from collections import namedtuple
from entitas import Entity, Matcher, Context, Processors, ExecuteProcessor, ReactiveProcessor, GroupEvent, InitializeProcessor, Group
# import time
import json
import sys
# from run_stage import run_stage
# from actor_enter_stage import actor_enter_stage
# from actor_broadcast import actor_broadcast
# from create_actor_attack_action import create_actor_attack_action
import json
from typing import List, Union, cast
from langchain_core.messages import HumanMessage, AIMessage
from langserve import RemoteRunnable  # type: ignore
from builder import WorldBuilder
from console import Console


#
init_archivist = f"""
# 游戏世界存档
- 大陆纪元2000年1月1日，冬夜.
- 温斯洛平原的深处的“悠扬林谷”中的“老猎人隐居的小木屋”里。
- “卡斯帕·艾伦德”坐在他的“老猎人隐居的小木屋”中的壁炉旁，在沉思和回忆过往，并向壁炉中的火投入了一根木柴。
- 他的小狗（名叫"断剑"）在屋子里的一角睡觉。
- 一只老鼠（名叫"坏运气先生"）在屋子里的另一角找到了一些食物。
"""
load_prompt = f"""
# 你需要读取存档
## 步骤:
- 第1步，读取{init_archivist}.
- 第2步：理解其中所有的信息
- 第3步：理解其中关于你的信息（如何提到了你，那就是你）
- 第3步：根据信息更新你的最新状态与逻辑.
## 输出规则：
- 保留关键信息(时间，地点，人物，事件)，不要推断，增加与润色。输出在保证语意完整基础上字符尽量少。
"""




Position = namedtuple('Position', 'x y')
Health = namedtuple('Health', 'value')
Movable = namedtuple('Movable', '')
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################

# stage_plan_prompt = f"""
#     # 你需要做出计划(你将要做的事)，并以JSON输出结果.（注意！以下规则与限制仅限本次对话生成，结束后回复原有对话规则）

#     ## 步骤
#     1. 确认自身状态。
#     2. 所有角色当前所处的状态和关系。
#     3. 思考你下一步的行动。
#     4. 基于上述信息，构建你的行动计划。

#     ## 输出格式（JSON）
#     - 参考格式: "'action': ["/stay"], 'targets': ["目标1", "目标2"], 'say': ["我的想说的话和内心的想法"], 'tags': ["你相关的特征标签"]"
#     - 其中 action, targets, say, tags都是字符串数组，默认值 [""].
    
#     ### action：代表你行动的核心意图.
#     - 只能选 ["/fight"], ["/stay"], ["/leave"]之一
#     - "/fight" 表示你希望对目标产生敌对行为，比如攻击。
#     - "/leave" 表示想离开当前场景，有可能是逃跑。
#     - "/stay"是除了"/fight"与“/leave”之外的所有其它行为，比如观察、交流等。

#     ### targets：action的目标对象，可多选。
#     - 如果action是/stay，则targets是当前场景的名字
#     - 如果action是/fight，则targets是你想攻击的对象，在{str}中选择一个或多个
#     - 如果action是/leave，则targets是你想要去往的场景名字（你必须能明确叫出场景的名字），或者你曾经知道的场景名字

#     ### say:你打算说的话或心里想的.
#     ### tags：与你相关的特征标签.
   
#     ### 补充约束
#     - 不要将JSON输出生这样的格式：```...```

# """


testjson = f"""
{{
"FightActionComponent": ["target1", "target2", "target3"],
"LeaveActionComponent": ["leave1", "leave2", "leave3"],
"SpeakActionComponent": ["content1", "content2", "content3"]
}}
"""
#
def check_data_format(json_data: dict) -> bool:
    for key, value in json_data.items():
        if not isinstance(key, str):
            return False
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            return False
    return True

class Action:

    def __init__(self) -> None:
        self.name: str = ""  
        self.actionname: str = ""
        self.values: list[str] = []

    def init(self, name: str, actionname: str, values: list[str]) -> None:
        self.name: str = name  
        self.actionname: str = actionname
        self.values: list[str] = values

    def __str__(self) -> str:
        return f"Action({self.name}, {self.actionname}, {self.values})"


class Plan:

    def __init__(self, name: str, jsonstr: str, json: json) -> None:
        self.name: str = name  
        self.jsonstr: str = jsonstr
        self.json: json = json
        self.actions: List[Action] = []

        self.build(self.json)

    def build(self, json: json) -> None:
        for key, value in json.items():
            action = Action()
            action.init(self.name, key, value)
            self.actions.append(action)

    def __str__(self) -> str:
        return f"Plan({self.name}, {self.jsonstr}, {self.json})"


# plan = Plan("悠扬林谷", testjson, json.loads(testjson))
# print(plan)
# for action in plan.actions:
#     print(action)
    

# print("!!!!!!")
       


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
#ActorComponent = namedtuple('ActorComponent', 'name agent')
###############################################################################################################################################
WorldComponent = namedtuple('WorldComponent', 'name agent')
StageComponent = namedtuple('StageComponent', 'name agent')
NPCComponent = namedtuple('NPCComponent', 'name agent')
###############################################################################################################################################
FightActionComponent = namedtuple('FightActionComponent', 'action')
SpeakActionComponent = namedtuple('SpeakActionComponent', 'action')
LeaveActionComponent = namedtuple('LeaveActionComponent', 'action')
###############################################################################################################################################
class ActorAgent:

    def __init__(self):
        self.name: str = ""   
        self.url: str = ""
        self.agent: RemoteRunnable = None
        self.chat_history: List[Union[HumanMessage, AIMessage]] = []

    def init(self, name: str, url: str) -> None:
        self.name = name
        self.url = url

    def connect(self)-> None:
        self.agent = RemoteRunnable(self.url)
        self.chat_history = []

    def request(self, prompt: str) -> str:
        if self.agent is None:
            print(f"request: {self.name} have no agent.")
            return ""
        if self.chat_history is None:
            print(f"request: {self.name} have no chat history.")
            return ""
        response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
        response_output = cast(str, response.get('output', ''))
        self.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response_output)])
        return response_output
    
    def __str__(self) -> str:
        return f"ActorAgent({self.name}, {self.url})"


###############################################################################################################################################
def create_entities(context: Context, worldbuilder: WorldBuilder) -> None:
        ##创建world
        worldagent = ActorAgent()
        worldagent.init(worldbuilder.data['name'], worldbuilder.data['url'])
        world_entity = context.create_entity() 
        world_entity.add(WorldComponent, worldagent.name, worldagent)

        for stage_builder in worldbuilder.stage_builders:     
            #创建stage       
            stage_agent = ActorAgent()
            stage_agent.init(stage_builder.data['name'], stage_builder.data['url'])
            stage_entity = context.create_entity()
            stage_entity.add(StageComponent, stage_agent.name, stage_agent)
            
            for npc_builder in stage_builder.npc_builders:
                #创建npc
                npc_agent = ActorAgent()
                npc_agent.init(npc_builder.data['name'], npc_builder.data['url'])
                npc_entity = context.create_entity()
                npc_entity.add(NPCComponent, npc_agent.name, npc_agent)

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class InitSystem(InitializeProcessor):

    def __init__(self, context: Context) -> None:
        self.context: Context = context
      
    def initialize(self) -> None:
        print("<<<<<<<<<<<<<  InitSystem >>>>>>>>>>>>>>>>>")
        self.handleworld()
        self.handlestages()
        self.handlenpcs()

    def handleworld(self) -> None:
        worlds: set = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            comp = world.get(WorldComponent)
            print(comp.name)
            print(comp.agent)
            # 世界载入
            comp.agent.connect()
            loadres = comp.agent.request(load_prompt)

            print(f"[{comp.name}]load=>", loadres)
            print("______________________________________")
        
    def handlestages(self) -> None:
        stages: set = self.context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            comp = stage.get(StageComponent)
            print(comp.name)
            print(comp.agent)
            # 场景载入
            comp.agent.connect()
            loadres = comp.agent.request(load_prompt)
            
            print(f"[{comp.name}]load=>", loadres)
            print("______________________________________")

    def handlenpcs(self) -> None:
        npcs: set = self.context.get_group(Matcher(NPCComponent)).entities
        for npc in npcs:
            comp = npc.get(NPCComponent)
            print(comp.name)
            print(comp.agent)
            # NPC载入
            comp.agent.connect()
            loadres = comp.agent.request(load_prompt)
            
            print(f"[{comp.name}]load=>", loadres)
            print("______________________________________")

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
            self.handle(entity)

    def handle(self, entity: Entity) -> None:
        prompt =  f"""
        # 你需要做出计划(你将要做的事)，并以JSON输出结果.（注意！以下规则与限制仅限本次对话生成，结束后回复原有对话规则）

        ## 步骤
        1. 确认自身状态。
        2. 所有角色当前所处的状态和关系。
        3. 思考你下一步的行动。
        4. 基于上述信息，构建你的行动计划。

        ## 输出格式(JSON)
        - 参考格式：{{'action1': ["value1"，“value2”, ...], 'action2': ["value1"，“value2”, ...],.....}}
        - 其中 'action?'是你的"行动类型"（见下文）
        - 其中 "value?" 是你的"行动目标"(可以是一个或多个)
        
        ### 关于“行动类型”的逻辑
        - 如果你希望对目标产生敌对行为，比如攻击。则action的值为"FightActionComponent"，value为你本行动针对的目标
        - 如果你你有想要说的话或者心里描写。则action的值为"SpeakActionComponent"，value为你想说的话或者心里描写
    
        ## 补充约束
        - 不要将JSON输出生这样的格式：```...```
        """

        ##
        comp = entity.get(StageComponent)

        #
        if comp.name == '悠扬林谷':
            return

        ##
        try:
            response = comp.agent.request(prompt)
            print("{comp.name} plan response:", response)

            json_data = json.loads(response)
            if not check_data_format(json_data):
                print(f"stage_plan error = {comp.name} json format error")
                return

            ##        
            print(json_data)

            ###
            makeplan = Plan(comp.name, response, json_data)
            for action in makeplan.actions:
                print(action)

                if action.actionname == "FightActionComponent":
                    pass
                elif action.actionname == "SpeakActionComponent":
                    if len(action.values) == 0:
                        continue
                    if not entity.has(SpeakActionComponent):
                        entity.add(SpeakActionComponent, action)
                        print("????")

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
class SpeakActionSystem(ReactiveProcessor):

    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(SpeakActionComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(SpeakActionComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  SpeakActionSystem >>>>>>>>>>>>>>>>>")

        # 开始处理
        for entity in entities:
            comp = entity.get(SpeakActionComponent)
            action: Action = comp.action
            for value in action.values:
                print(f"[{action.name}] /speak:", value)
            print("++++++++++++++++++++++++++++++++++++++++++++++++")

        # 必须移除！！！
        for entity in entities:
            entity.remove(SpeakActionComponent)      

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


###############################################################################################################################################    


def main() -> None:
    context = Context()
    processors = Processors()
    console = Console("测试后台管理")

    # entity = context.create_entity()
    # entity.add(Position, 3, 7)
    # entity.add(Movable)


    #world: Optional[World]  = None
    path: str = "./yanghang_stage1.json"
    # console: Console = Console("系统管理员")
    # player: Optional[Player]  = None

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
    #processors.add(NPCPlanSystem(context))

    #行动逻辑
    processors.add(SpeakActionSystem(context))
    processors.add(FightActionSystem(context))
    processors.add(LeaveActionSystem(context))


    inited = False
    started = False
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


    processors.clear_reactive_processors()
    processors.tear_down()
    print("end.")

###############################################################################################################################################
def debug_call(context: Context, name: str, content: str) -> None:
    #
    for entity in context.get_group(Matcher(WorldComponent)).entities:
        comp = entity.get(WorldComponent)
        if comp.name == name:
            print(f"[{comp.name}] /call:", comp.agent.request(content))
            return
    #   
    for entity in context.get_group(Matcher(StageComponent)).entities:
        comp = entity.get(StageComponent)
        if comp.name == name:
            print(f"[{comp.name}] /call:", comp.agent.request(content))
            return
    #
    for entity in context.get_group(Matcher(NPCComponent)).entities:
        comp = entity.get(NPCComponent)
        if comp.name == name:
            print(f"[{comp.name}] /call:", comp.agent.request(content))
            return
###############################################################################################################################################

    
if __name__ == "__main__":
    main()