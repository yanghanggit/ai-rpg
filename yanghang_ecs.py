
from collections import namedtuple
from entitas import Entity, Matcher, Context, Processors, ExecuteProcessor, ReactiveProcessor, GroupEvent, InitializeProcessor, Group, EntityIndex, PrimaryEntityIndex
import json
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

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
WorldComponent = namedtuple('WorldComponent', 'name agent')
StageComponent = namedtuple('StageComponent', 'name agent events')
NPCComponent = namedtuple('NPCComponent', 'name agent current_stage')
###############################################################################################################################################

###############################################################################################################################################
SpeakActionComponent = namedtuple('SpeakActionComponent', 'action')
FightActionComponent = namedtuple('FightActionComponent', 'action')
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
        - action值不允许出现FightActionComponent，SpeakActionComponent之外的值
    
        ## 补充约束
        - 不要将JSON输出生这样的格式：```...```
        """

        ##
        comp = entity.get(StageComponent)
        ##
        try:
            response = comp.agent.request(prompt)
            #print("{comp.name} plan response:", response)

            json_data = json.loads(response)
            if not check_data_format(json_data):
                print(f"stage_plan error = {comp.name} json format error")
                return

            ##        
            #print(json_data)

            ###
            makeplan = Plan(comp.name, response, json_data)
            for action in makeplan.actions:
                print(action)

                if len(action.values) == 0:
                    continue

                if action.actionname == "FightActionComponent":
                    if not entity.has(FightActionComponent):
                        entity.add(FightActionComponent, action)

                elif action.actionname == "SpeakActionComponent":
                    if not entity.has(SpeakActionComponent):
                        entity.add(SpeakActionComponent, action)
                else:
                    print(f"error {action.actionname}, action value")
                    continue

        except Exception as e:
            print(f"stage_plan error = {e}")
            return
        return
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
        - 如果你有想要说的话或者心里描写。则action的值为"SpeakActionComponent"，value为你想说的话或者心里描写
        - 如果表示想离开当前场景，有可能是逃跑。action的值为"LeaveActionComponent"，value是你想要去往的场景名字（你必须能明确叫出场景的名字），或者你曾经知道的场景名字
        - action值不允许出现FightActionComponent，SpeakActionComponent，LeaveActionComponent之外的值

        ## 补充约束
        - 不要将JSON输出生这样的格式：```...```
        """

        ##
        comp = entity.get(NPCComponent)
        ##
        try:
            response = comp.agent.request(prompt)
            #print("{comp.name} plan response:", response)

            json_data = json.loads(response)
            if not check_data_format(json_data):
                print(f"stage_plan error = {comp.name} json format error")
                return

            ##        
            #print(json_data)

            ###
            makeplan = Plan(comp.name, response, json_data)
            for action in makeplan.actions:
                print(action)

                if len(action.values) == 0:
                    print(f"stage_plan error = {comp.name} action values error is empty")
                    continue

                if action.actionname == "FightActionComponent":
                    if not entity.has(FightActionComponent):
                        entity.add(FightActionComponent, action)
                
                elif action.actionname == "LeaveActionComponent":
                    if not entity.has(LeaveActionComponent):
                        entity.add(LeaveActionComponent, action)

                elif action.actionname == "SpeakActionComponent":
                    if not entity.has(SpeakActionComponent):
                        entity.add(SpeakActionComponent, action)
                else:
                    print(f"error {action.actionname}, action value")

        except Exception as e:
            print(f"stage_plan error = {e}")
            return
        return    
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
            #print(entity.get(FightActionComponent).context)
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
                stagecomp = self.getstage(entity)
                if stagecomp is not None:
                    stagecomp.events.append(f"{action.name} 说（或者心里活动）: {value}")

            print("++++++++++++++++++++++++++++++++++++++++++++++++")

        # 必须移除！！！
        for entity in entities:
            entity.remove(SpeakActionComponent)     

    def getstage(self, entity: Entity) -> StageComponent:
        if entity.has(StageComponent):
            return entity.get(StageComponent)

        elif entity.has(NPCComponent):
            current_stage_name = entity.get(NPCComponent).current_stage
            for stage in self.context.get_group(Matcher(StageComponent)).entities:
                if stage.get(StageComponent).name == current_stage_name:
                    return stage.get(StageComponent)
        return None
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
            #print(entity.get(LeaveActionComponent).context)
            entity.remove(LeaveActionComponent)    
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################               
class DirectorSystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DirectorSystem >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            self.handle(entity)
            #清空
            comp = entity.get(StageComponent)
            comp.events.clear() #不能 = []，会报错！！！

    def handle(self, entity: Entity) -> None:
        comp = entity.get(StageComponent)
        print(f"[{comp.name}] 开始导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")
        if len(comp.events) == 0:
            return
    
        #debug
        for event in comp.events:
            print("moive:", event)

        allevents = "\n".join(comp.events)
        director_prompt =  f"""
        # 你按着我的给你的脚本来演绎过程，并适当润色让过程更加生动。
        ## 剧本如下
        - {allevents}
        ## 步骤
        - 第1步：理解我的剧本
        - 第2步：根据剧本，完善你的故事讲述(同一个人物的行为描述要合并处理)。要保证和脚本的结果一致。
        - 第3步：更新你的记忆
        ## 输出规则
        - 输出在保证语意完整基础上字符尽量少。
        """
        #
        response = comp.agent.request(director_prompt)
        print("============================================================================")

        print(f"{comp.name}=>", response)


        npccomps = self.getnpcs(comp.name)
        all_names = "、".join([ncomp.name for ncomp in npccomps])

        confirm_prompt = f"""
        # 你目睹或者参与了这一切，并更新了你的记忆
        - {response}
        # 你能确认
        - {all_names} 都还存在。
        """

        for ncomp in npccomps:
            response = ncomp.agent.request(confirm_prompt)
            print(f"[{ncomp.name}]=>", response)


        print(f"[{comp.name}] 结束导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")


    def getnpcs(self, stage: str) -> List[NPCComponent]:
        npcs = []
        for entity in self.context.get_group(Matcher(NPCComponent)).entities:
            if entity.get(NPCComponent).current_stage == stage:
                npcs.append(entity.get(NPCComponent))
        return npcs


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
def main() -> None:

    context = Context()
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

    #行动结束后导演
    processors.add(DirectorSystem(context))
    
    ####
    inited:bool = False
    started:bool = False
    who: str = ""

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
            print(f"/who 你现在控制了=>", who)

        elif "/attack" in usr_input:
            if not started:
                print("请先/run")
                continue
            command = "/attack"
            target_name = console.parse_command(usr_input, command)    
            debug_attack(context, who, target_name)
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
def debug_attack(context: Context, src: str, dest: str) -> None:
    print(f"debug_attack: {src} attack {dest}")

    # parse_res: tuple[str, str] = console.parse_at_symbol(input_content)
    #         target = parse_res[0]
    #         content = parse_res[1]

    srcentity_info: tuple[Entity, NPCComponent] = debug_get_npc(context, src)
    ensrc = srcentity_info[0]
    compsrc = srcentity_info[1]
    if ensrc is None:
        print(f"debug_attack error: {src} not found")
        return
        
    destentity_info = debug_get_npc(context, dest)
    endest = destentity_info[0]
    compdest = destentity_info[1]
    if endest is None:
        print(f"debug_attack error: {dest} not found")
        return
    
    if not ensrc.has(FightActionComponent):
        action = Action()
        action.init(compsrc.name, "FightActionComponent", [str])
        ensrc.add(FightActionComponent, action)
        print(f"debug_attack: {src} add {action}")
###############################################################################################################################################
def debug_get_npc(context: Context, name: str) -> tuple[Entity, NPCComponent]:
    # for entity in context.get_group(Matcher(WorldComponent)).entities:
    #     comp = entity.get(WorldComponent)
    #     if comp.name == name:
    #         return entity, WorldComponent
    
    # for entity in context.get_group(Matcher(StageComponent)).entities:
    #     comp = entity.get(StageComponent)
    #     if comp.name == name:
    #         return entity, StageComponent
        
    for entity in context.get_group(Matcher(NPCComponent)).entities:
        comp = entity.get(NPCComponent)
        if comp.name == name:
            return entity, NPCComponent

    return None, None

###############################################################################################################################################

    
if __name__ == "__main__":
    main()