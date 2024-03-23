#pip install pandas openpyxl
import pandas as pd
import os
from loguru import logger
from pandas.core.frame import DataFrame
import json
from typing import List, Dict, Any

##全局的，方便，不封装了，反正当工具用
# 核心设置
WORLD_NAME = "budding_world"

#模版
GPT_AGENT_TEMPLATE = "gpt_agent_template.py"
NPC_SYS_PROMPT_TEMPLATE = "npc_sys_prompt_template.md"
STAGE_SYS_PROMPT_TEMPLATE = "stage_sys_prompt_template.md"

#默认rag
RAG_FILE = "rag.md"

## 输出路径
OUT_PUT_NPC_SYS_PROMPT = "gen_npc_sys_prompt"
OUT_PUT_STAGE_SYS_PROMPT = "gen_stage_sys_prompt"
OUT_PUT_AGENT = "gen_agent"

def readmd(file_path: str) -> str:
    try:
        file_path = os.getcwd() + file_path
        with open(file_path, 'r', encoding='utf-8') as file:
            md_content = file.read()
            if isinstance(md_content, str):
                return md_content
            else:
                logger.error(f"Failed to read the file:{md_content}")
                return ""
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"An error occurred: {e}"
    

def readpy(file_path: str) -> str:
    try:
        file_path = os.getcwd() + file_path
        with  open(file_path, 'r', encoding='utf-8') as file:
            pystr = file.read()
            if isinstance(pystr, str):
                return pystr
            else:
                logger.error(f"Failed to read the file:{pystr}")
                return ""

    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"An error occurred: {e}"
    

class ExcelNPC:

    def __init__(self, name: str, codename: str, description: str, history: str, gptmodel: str, port: int, api: str, worldview: str) -> None:
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.history: str = history
        self.gptmodel: str = gptmodel
        self.port: int = port
        self.api: str = api
        self.worldview: str = worldview

        self.sysprompt: str = ""
        self.agentpy: str = ""

        logger.info(self.localhost_api())

    def __str__(self) -> str:
        return f"ExcelNPC({self.name}, {self.codename}, {self.description}, {self.gptmodel}, {self.port}, {self.api}, {self.worldview})"
        
    def isvalid(self) -> bool:
        return True
    
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        genprompt = str(sys_prompt_template)
        genprompt = genprompt.replace("<%name>", self.name)
        genprompt = genprompt.replace("<%description>", self.description)
        genprompt = genprompt.replace("<%history>", self.history)
        self.sysprompt = genprompt
        return self.sysprompt
    
    def gen_agentpy(self, agent_py_template: str) -> str:
        agentpy = str(agent_py_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{WORLD_NAME}/{self.worldview}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{WORLD_NAME}/{OUT_PUT_NPC_SYS_PROMPT}/{self.codename}_sys_prompt.md""")
        agentpy = agentpy.replace("<%GPT_MODEL>", self.gptmodel)
        agentpy = agentpy.replace("<%PORT>", str(self.port))
        agentpy = agentpy.replace("<%API>", self.api)
        self.agentpy = agentpy
        return self.agentpy
    
    def localhost_api(self) -> str:
        return f"http://localhost:{self.port}{self.api}/"

class ExcelStage:

    def __init__(self, name: str, codename: str, description: str, gptmodel: str, port: int, api: str, worldview: str) -> None:
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.gptmodel: str = gptmodel
        self.port: int = port
        self.api: str = api
        self.worldview: str = worldview

        self.sysprompt: str = ""
        self.agentpy: str = ""

        logger.info(self.localhost_api())

    def __str__(self) -> str:
        return f"ExcelStage({self.name}, {self.codename}, {self.description}, {self.gptmodel}, {self.port}, {self.api}, {self.worldview})"
        
    def isvalid(self) -> bool:
        return True
    
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        genprompt = str(sys_prompt_template)
        genprompt = genprompt.replace("<%name>", self.name)
        genprompt = genprompt.replace("<%description>", self.description)
        self.sysprompt = genprompt
        return self.sysprompt
    
    def gen_agentpy(self, agent_py_template: str) -> str:
        agentpy = str(agent_py_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{WORLD_NAME}/{self.worldview}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{WORLD_NAME}/{OUT_PUT_STAGE_SYS_PROMPT}/{self.codename}_sys_prompt.md""")
        agentpy = agentpy.replace("<%GPT_MODEL>", self.gptmodel)
        agentpy = agentpy.replace("<%PORT>", str(self.port))
        agentpy = agentpy.replace("<%API>", self.api)
        self.agentpy = agentpy
        return self.agentpy
    
    def localhost_api(self) -> str:
        return f"http://localhost:{self.port}{self.api}/"
    

class ExcelProp:
    
    def __init__(self, name: str, codename: str, isunique: str, description: str, worldview: str) -> None:
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.isunique: str = isunique
        self.worldview: str = worldview

        self.sysprompt: str = ""
        self.agentpy: str = ""

    def __str__(self) -> str:
        return f"TblProp({self.name}, {self.codename}, {self.isunique}, {self.description}, {self.worldview})"
        
    def isvalid(self) -> bool:
        return True
        
       

##全局的，方便，不封装了，反正当工具用
npc_sys_prompt_template: str = readmd(f"/{WORLD_NAME}/{NPC_SYS_PROMPT_TEMPLATE}")
stage_sys_prompt_template: str = readmd(f"/{WORLD_NAME}/{STAGE_SYS_PROMPT_TEMPLATE}")
gpt_agent_template: str = readpy(f"/{WORLD_NAME}/{GPT_AGENT_TEMPLATE}")


npcsheet: DataFrame = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='NPC', engine='openpyxl')
stagesheet: DataFrame = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='Stage', engine='openpyxl')
propsheet: DataFrame = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='Prop', engine='openpyxl')

excelnpcs: list[ExcelNPC] = []
excelstages: list[ExcelStage] = []    
excelprops: list[ExcelProp] = []


############################################################################################################
def gennpcs() -> None:

    ## 读取Excel文件
    for index, row in npcsheet.iterrows():
        excelnpc = ExcelNPC(row["name"], row["codename"], row["description"], row["history"], row["GPT_MODEL"], row["PORT"], row["API"], RAG_FILE)
        if not excelnpc.isvalid():
            #print(f"Invalid row: {excelnpc}")
            continue
        excelnpc.gen_sys_prompt(npc_sys_prompt_template)
        excelnpc.gen_agentpy(gpt_agent_template)
        excelnpcs.append(excelnpc)

    for excelnpc in excelnpcs:
        directory = f"{WORLD_NAME}/{OUT_PUT_NPC_SYS_PROMPT}"
        filename = f"{excelnpc.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(excelnpc.sysprompt)
            file.write("\n\n\n")

    for excelnpc in excelnpcs:
        directory = f"{WORLD_NAME}/{OUT_PUT_AGENT}"
        filename = f"{excelnpc.codename}_agent.py"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(excelnpc.agentpy)
            file.write("\n\n\n")

############################################################################################################
def genstages() -> None:
   
    ## 读取Excel文件
    for index, row in stagesheet.iterrows():
        excelstage = ExcelStage(row["name"], row["codename"], row["description"], row["GPT_MODEL"], row["PORT"], row["API"], RAG_FILE)
        if not excelstage.isvalid():
            #print(f"Invalid row: {excelstage}")
            continue
        excelstage.gen_sys_prompt(stage_sys_prompt_template)
        excelstage.gen_agentpy(gpt_agent_template)
        excelstages.append(excelstage)

    for excelstage in excelstages:
        directory = f"{WORLD_NAME}/{OUT_PUT_STAGE_SYS_PROMPT}"
        filename = f"{excelstage.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(excelstage.sysprompt)
            file.write("\n\n\n")

    for excelstage in excelstages:
        directory = f"{WORLD_NAME}/{OUT_PUT_AGENT}"
        filename = f"{excelstage.codename}_agent.py"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(excelstage.agentpy)
            file.write("\n\n\n")

############################################################################################################
def genprops() -> None:
    ## 读取Excel文件
    for index, row in propsheet.iterrows():
        excelprop = ExcelProp(row["name"], row["codename"], row["isunique"], row["description"], RAG_FILE)
        if not excelprop.isvalid():
            #(f"Invalid row: {excelprop}")
            continue
        excelprops.append(excelprop)

############################################################################################################
def analyze_npc_relationship_graph() -> None:
    npc_json_str: str = npcsheet.to_json(orient='records', force_ascii=False)
    npcarray: List[str] = json.loads(npc_json_str)
 
    # 以名字为key, 将description和history合并，作为总内容。里面可能含有其他人的名字
    npcgraph_name_description_history: Dict[str, str] = {}
    for npc in npcarray:
        key = npc["name"]
        content = f"{npc['description']} {npc['history']}"
        npcgraph_name_description_history[key] = content

    #key是名字，value是在他们的description与history里提到这个名字的人
    relationship_graph: Dict[str, List[str]] = {}
    # 遍历每一个名字
    for name in npcgraph_name_description_history:
        # 初始化关系列表
        who_mentioned_you = []
        
        # 遍历每一个名字的关系内容
        for other_name, content in npcgraph_name_description_history.items():
            # 如果A的名字出现在B的content里，就加入A的who_mentioned_you
            if name != other_name and name in content:
                who_mentioned_you.append(other_name)
        
        # 将关系列表加入数据结构
        relationship_graph[name] = who_mentioned_you

    # 最后遍历这个relationship_graph，其中的value部分代表着‘who_mentioned_you’。
    # 例如，name为A，who_mentioned_you = [B,C]代表着B和C都提到了A。
    # 这样请在relationship_graph结构里索引B或C,如果他们的‘who_mentioned_you’没有A，
    # 代表着A没提到B或C，凡是满足这个情况的，就答应log来报警
    for name, mentioned in relationship_graph.items():
        for person in mentioned:
            if name not in relationship_graph.get(person, []):
                logger.warning(f"{person} mentioned {name}, but {name} did not mention {person}")

############################################################################################################
def analyze_relationship_graph_betweennpcs_and_props() -> None:
    
    npc_json_str: str = npcsheet.to_json(orient='records', force_ascii=False)
    npcarray: List[str] = json.loads(npc_json_str)

    prop_json_str: str = propsheet.to_json(orient='records', force_ascii=False)
    proparray: List[str] = json.loads(prop_json_str)

    # 以名字为key, 将description和history合并，作为总内容。里面可能含有其他人的名字
    npcgraph_name_description_history: Dict[str, str] = {}
    for npc in npcarray:
        key = npc["name"]
        content = f"{npc['description']} {npc['history']}"
        npcgraph_name_description_history[key] = content

    # 以名字为key, 将description合并，作为总内容。里面可能含有其他人的名字
    propgraph_name_description: Dict[str, str] = {}
    for prop in proparray:
        key = prop["name"]
        content = f"{prop['description']}"
        propgraph_name_description[key] = content

    ##分析道具有谁提到了这个道具，并输出
    prop_mentions: Dict[str, List[str]] = {}
    for prop_name, prop_description in propgraph_name_description.items():
        mentioned_by = []
        for npc_name, npc_content in npcgraph_name_description_history.items():
            if prop_name in npc_content:
                mentioned_by.append(npc_name)
        prop_mentions[prop_name] = mentioned_by

    ## 有哪些人提到了这个道具
    for prop_name, mentioned_by in prop_mentions.items():
        if mentioned_by and len(mentioned_by) > 0:
            logger.warning(f"{prop_name}: {mentioned_by}")

############################################################################################################
def main() -> None:
    gennpcs()
    genstages()
    genprops()
    analyze_npc_relationship_graph()
    analyze_relationship_graph_betweennpcs_and_props()

if __name__ == "__main__":
    main()




#graph structure

#name, [names,......]
# npcgraph: Dict[str, List[str]] = {}
# stagegraph: Dict[str, List[str]] = {}
# propgraph: Dict[str, List[str]] = {}
#stage_json_str: str = stagesheet.to_json(orient='records', force_ascii=False)
#prop_json_str: str = propsheet.to_json(orient='records', force_ascii=False)
# stagearray = json.loads(stage_json_str)
# proparray = json.loads(prop_json_str)
#