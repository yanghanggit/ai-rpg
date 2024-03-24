#pip install pandas openpyxl
import pandas as pd
import os
from loguru import logger
from pandas.core.frame import DataFrame
import json
from typing import List, Dict, Any, Optional

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
    

class ExcelDataNPC:

    def __init__(self, name: str, codename: str, description: str, history: str, gptmodel: str, port: int, api: str, worldview: str) -> None:
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.history: str = history
        self.gptmodel: str = gptmodel
        self.port: int = port
        self.api: str = api
        self.worldview: str = worldview
        self.desc_and_history: str = f"""{self.description} {self.history}"""
        self.mentioned_npcs: List[str] = []
        self.mentioned_props: List[str] = []

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
    
    def write_sys_prompt(self) -> None: 
        directory = f"{WORLD_NAME}/{OUT_PUT_NPC_SYS_PROMPT}"
        filename = f"{self.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(self.sysprompt)
            file.write("\n\n\n")

    def write_agentpy(self) -> None:
        directory = f"{WORLD_NAME}/{OUT_PUT_AGENT}"
        filename = f"{self.codename}_agent.py"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(self.agentpy)
            file.write("\n\n\n")

    def add_mentioned_npc(self, name: str) -> bool:
        if name == self.name:
            return False
        if name in self.mentioned_npcs:
            return True
        if name in self.desc_and_history:
            self.mentioned_npcs.append(name)
            return True
        return False
    
    def check_mentioned_npc(self, name: str) -> bool:
        if name in self.mentioned_npcs:
            return True
        return False
    
    def add_mentioned_prop(self, name: str) -> bool:
        if name in self.mentioned_props:
            return True
        if name in self.desc_and_history:
            self.mentioned_props.append(name)
            return True
        return False
    
    def check_mentioned_prop(self, name: str) -> bool:
        if name in self.mentioned_props:
            return True
        return False


class ExcelDataStage:

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
    

    def write_sys_prompt(self) -> None: 
        directory = f"{WORLD_NAME}/{OUT_PUT_STAGE_SYS_PROMPT}"
        filename = f"{self.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(self.sysprompt)
            file.write("\n\n\n")

    def write_agentpy(self) -> None:
        directory = f"{WORLD_NAME}/{OUT_PUT_AGENT}"
        filename = f"{self.codename}_agent.py"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(self.agentpy)
            file.write("\n\n\n")
    

class ExcelDataProp:
    
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

excelnpcs: list[ExcelDataNPC] = []
excelstages: list[ExcelDataStage] = []    
excelprops: list[ExcelDataProp] = []

dict_excelnpcs: Dict[str, ExcelDataNPC] = {}
dict_excelstages: Dict[str, ExcelDataStage] = {}
dict_excelprops: Dict[str, ExcelDataProp] = {}

npcsheet: DataFrame = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='NPC', engine='openpyxl')
stagesheet: DataFrame = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='Stage', engine='openpyxl')
propsheet: DataFrame = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='Prop', engine='openpyxl')
####测试的一个世界编辑
world1sheet: DataFrame = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='World1', engine='openpyxl')

############################################################################################################
def gennpcs() -> None:
    ## 读取Excel文件
    for index, row in npcsheet.iterrows():
        excelnpc = ExcelDataNPC(row["name"], row["codename"], row["description"], row["history"], row["GPT_MODEL"], row["PORT"], row["API"], RAG_FILE)
        if not excelnpc.isvalid():
            #print(f"Invalid row: {excelnpc}")
            continue
        excelnpcs.append(excelnpc)
        excelnpc.gen_sys_prompt(npc_sys_prompt_template)
        excelnpc.write_sys_prompt()
        excelnpc.gen_agentpy(gpt_agent_template)
        excelnpc.write_agentpy()
        dict_excelnpcs[excelnpc.name] = excelnpc

############################################################################################################
def genstages() -> None:
    ## 读取Excel文件
    for index, row in stagesheet.iterrows():
        excelstage = ExcelDataStage(row["name"], row["codename"], row["description"], row["GPT_MODEL"], row["PORT"], row["API"], RAG_FILE)
        if not excelstage.isvalid():
            #print(f"Invalid row: {excelstage}")
            continue
        excelstages.append(excelstage)
        excelstage.gen_sys_prompt(stage_sys_prompt_template)
        excelstage.write_sys_prompt()
        excelstage.gen_agentpy(gpt_agent_template)
        excelstage.write_agentpy()    
        dict_excelstages[excelstage.name] = excelstage 
############################################################################################################
def genprops() -> None:
    ## 读取Excel文件
    for index, row in propsheet.iterrows():
        excelprop = ExcelDataProp(row["name"], row["codename"], row["isunique"], row["description"], RAG_FILE)
        if not excelprop.isvalid():
            #(f"Invalid row: {excelprop}")
            continue
        excelprops.append(excelprop)
        dict_excelprops[excelprop.name] = excelprop
############################################################################################################
def analyze_npc_relationship_graph() -> None:
    #先构建
    for npc in dict_excelnpcs.values():
        npc.mentioned_npcs.clear()
        for other_npc in dict_excelnpcs.values():
            if npc.add_mentioned_npc(other_npc.name):
                logger.info(f"{npc.name} mentioned {other_npc.name}")

    #再检查
    for npc in dict_excelnpcs.values():
        for other_npc in dict_excelnpcs.values():
            if npc.check_mentioned_npc(other_npc.name) and not other_npc.check_mentioned_npc(npc.name):
                logger.warning(f"{npc.name} mentioned {other_npc.name}, but {other_npc.name} did not mention {npc.name}")

################################################################################################################
def analyze_relationship_graph_betweennpcs_and_props() -> None:
    #先构建
    for npc in dict_excelnpcs.values():
        npc.mentioned_props.clear()
        for other_prop in dict_excelprops.values():
            if npc.add_mentioned_prop(other_prop.name):
                logger.info(f"{npc.name} mentioned {other_prop.name}")
    #再检查
    for npc in dict_excelnpcs.values():
        if len(npc.mentioned_props) > 0:
            logger.warning(f"{npc.name}: {npc.mentioned_props}")
################################################################################################################   
class ExcelEditorNPC:
    def __init__(self, data: Any) -> None:
        self.data: Any = data
        self.excelnpc: Optional[ExcelDataNPC] = None
        self.excelprops: List[ExcelDataProp] = []
        self.initialization_memory: str = ""

        if self.data["type"] not in ["AdminNPC", "PlayerNPC", "NPC"]:
            logger.error(f"Invalid NPC type: {self.data['type']}")
            return
        
        self.parsefiles()
        self.parse_initialization_memory()
        
    def parsefiles(self) -> None:
        filesdata: str = self.data["files"]
        if filesdata is None:
            return        
        files = filesdata.split(";")
        for file in files:
            if file in dict_excelprops:
                self.excelprops.append(dict_excelprops[file])
            else:
                logger.error(f"Invalid file: {file}")

    def parse_initialization_memory(self) -> None:
        initialization_memory = self.data["initialization_memory"]
        if initialization_memory is None:
            return
        self.initialization_memory = str(initialization_memory)

    def __str__(self) -> str:
        propsstr = ', '.join(str(prop) for prop in self.excelprops)
        return f"EditorNPC({self.data['name']}, {self.data['type']}, files: {propsstr}, initialization_memory: {self.initialization_memory})"
   
################################################################################################################
class ExcelEditorStage:
    def __init__(self, data: Any) -> None:
        self.data: Any = data

        #数据
        self.stage_entry_conditions: List[str] = []
        self.stage_exit_conditions: List[str] = []
        self.props_in_stage: List[str] = []
        self.npcs_in_stage: List[str] = []
        self.initialization_memory: str = ""

        if self.data["type"] not in ["Stage"]:
            logger.error(f"Invalid Stage type: {self.data['type']}")
            return

        #分析数据
        self.parse_stage_entry_conditions()
        self.parse_stage_exit_conditions()
        self.parse_props_in_stage()
        self.parse_npcs_in_stage()
        self.parse_initialization_memory()

    def parse_stage_entry_conditions(self) -> None:
        stage_entry_conditions = self.data["stage_entry_conditions"]
        if stage_entry_conditions is None:
            return        
        self.stage_entry_conditions = stage_entry_conditions.split(";")

    def parse_stage_exit_conditions(self) -> None:
        stage_exit_conditions = self.data["stage_exit_conditions"]
        if stage_exit_conditions is None:
            return
        self.stage_exit_conditions = stage_exit_conditions.split(";")

    def parse_props_in_stage(self) -> None:
        props_in_stage = self.data["props_in_stage"]
        if props_in_stage is None:
            return
        self.props_in_stage = props_in_stage.split(";")

    def parse_npcs_in_stage(self) -> None:
        npcs_in_stage = self.data["npcs_in_stage"]
        if npcs_in_stage is None:
            return
        self.npcs_in_stage = npcs_in_stage.split(";")

    def parse_initialization_memory(self) -> None:
        initialization_memory = self.data["initialization_memory"]
        if initialization_memory is None:
            return
        self.initialization_memory = str(initialization_memory)

    def __str__(self) -> str:
        return f"EditorStage({self.data["name"]}, {self.data["type"]}, stage_entry_conditions: {self.stage_entry_conditions}, stage_exit_conditions: {self.stage_exit_conditions}, props_in_stage: {self.props_in_stage}, npcs_in_stage: {self.npcs_in_stage}, initialization_memory: {self.initialization_memory})"

################################################################################################################
class ExcelEditorWorld:
    def __init__(self, data: List[Any]) -> None:
        # 根数据
        self.data: List[Any] = data
        # 解析数据用
        self.data_adminnpcs: List[Any] = []
        self.data_playernpcs: List[Any] = []
        self.data_npcs: List[Any] = []
        self.data_stages: List[Any] = []
        #构建数据
        self.editor_adminnpcs: List[ExcelEditorNPC] = []
        self.editor_playernpcs: List[ExcelEditorNPC] = []
        self.editor_npcs: List[ExcelEditorNPC] = []
        self.editor_stages: List[ExcelEditorStage] = []
        ##构建流程
        self.build_and_categorize_data()
        ##
        self.build_editor_adminnpcs()
        self.build_editor_playernpcs()
        self.build_editor_npcs()
        self.build_editor_stages()

    #先将数据分类
    def build_and_categorize_data(self) -> None:
        for item in self.data:
            if item["type"] == "AdminNPC":
                self.data_adminnpcs.append(item)
            elif item["type"] == "PlayerNPC":
                self.data_playernpcs.append(item)
            elif item["type"] == "NPC":
                self.data_npcs.append(item)
            elif item["type"] == "Stage":
                self.data_stages.append(item)

    def build_editor_adminnpcs(self) -> None:
        for item in self.data_adminnpcs:
            editor_npc = ExcelEditorNPC(item)
            self.editor_adminnpcs.append(editor_npc)
            logger.info(editor_npc)

    def build_editor_playernpcs(self) -> None:
        for item in self.data_playernpcs:
            editor_npc = ExcelEditorNPC(item)
            self.editor_playernpcs.append(editor_npc)
            logger.info(editor_npc)
       
    def build_editor_npcs(self) -> None:
        for item in self.data_npcs:
            editor_npc = ExcelEditorNPC(item)
            self.editor_npcs.append(editor_npc)
            logger.info(editor_npc)

    def build_editor_stages(self) -> None:
        for item in self.data_stages:
            editor_stage = ExcelEditorStage(item)
            self.editor_stages.append(editor_stage)
            logger.info(editor_stage)

    #最后生成JSON
    def buildworld(self) -> None:
        logger.warning("Building world..., 需要检查，例如NPC里出现了，但是场景中没有出现，那就是错误。一顿关联，最后生成JSON文件")

############################################################################################################
def gen_world1() -> None:
    world1_sheet_str: str = world1sheet.to_json(orient='records', force_ascii=False)
    world1data: List[Any] = json.loads(world1_sheet_str)
    #logger.info(world1data)
    worldeditor = ExcelEditorWorld(world1data)
    worldeditor.buildworld()

############################################################################################################
def main() -> None:
    gennpcs()
    genstages()
    genprops()
    analyze_npc_relationship_graph()
    analyze_relationship_graph_betweennpcs_and_props()
    gen_world1() #测试这个世界编辑

if __name__ == "__main__":
    main()
