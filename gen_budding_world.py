#pip install pandas openpyxl
import pandas as pd
import os
from loguru import logger


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
    

class ExcelProp:
    
    def __init__(self, name: str, codename: str, description: str, worldview: str) -> None:
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.worldview: str = worldview

        self.sysprompt: str = ""
        self.agentpy: str = ""

    def __str__(self) -> str:
        return f"TblProp({self.name}, {self.codename}, {self.description}, {self.worldview})"
        
    def isvalid(self) -> bool:
        return True
        
       

##全局的，方便，不封装了，反正当工具用
npc_sys_prompt_template = readmd(f"/{WORLD_NAME}/{NPC_SYS_PROMPT_TEMPLATE}")
stage_sys_prompt_template = readmd(f"/{WORLD_NAME}/{STAGE_SYS_PROMPT_TEMPLATE}")
gpt_agent_template = readpy(f"/{WORLD_NAME}/{GPT_AGENT_TEMPLATE}")


npcsheet = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='NPC', engine='openpyxl')
stagesheet = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='Stage', engine='openpyxl')
propsheet = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='Prop', engine='openpyxl')

excelnpcs: list[ExcelNPC] = []
excelstages: list[ExcelStage] = []    
excelprops: list[ExcelProp] = []


def gennpcs() -> None:

    ## 读取Excel文件
    for index, row in npcsheet.iterrows():
        excelnpc = ExcelNPC(row["name"], row["codename"], row["description"], row["history"], row["GPT_MODEL"], row["PORT"], row["API"], RAG_FILE)
        if not excelnpc.isvalid():
            print(f"Invalid row: {excelnpc}")
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


def genstages() -> None:
   
    ## 读取Excel文件
    for index, row in stagesheet.iterrows():
        excelstage = ExcelStage(row["name"], row["codename"], row["description"], row["GPT_MODEL"], row["PORT"], row["API"], RAG_FILE)
        if not excelstage.isvalid():
            print(f"Invalid row: {excelstage}")
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


def genprops() -> None:
    ## 读取Excel文件
    for index, row in propsheet.iterrows():
        excelprop = ExcelProp(row["name"], row["codename"], row["description"], RAG_FILE)
        if not excelprop.isvalid():
            print(f"Invalid row: {excelprop}")
            continue
        excelprops.append(excelprop)













def main() -> None:
    gennpcs()
    genstages()
    genprops()

if __name__ == "__main__":
    main()
