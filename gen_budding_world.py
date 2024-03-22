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

def read_md(file_path: str) -> str:
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
    

def read_py(file_path: str) -> str:
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
    

class TblNpc:

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
        return f"TblNpc({self.name}, {self.codename}, {self.description}, {self.history}, {self.gptmodel}, {self.port}, {self.api}, {self.worldview})"
        
    def isvalid(self) -> bool:
        return True
    
    def gen_sys_prompt(self, orgin_npc_template: str) -> str:
        npc_prompt = str(orgin_npc_template)
        npc_prompt = npc_prompt.replace("<%name>", self.name)
        npc_prompt = npc_prompt.replace("<%description>", self.description)
        npc_prompt = npc_prompt.replace("<%history>", self.history)
        self.sysprompt = npc_prompt
        return self.sysprompt
    
    def gen_agentpy(self, orgin_agent_template: str) -> str:
        agentpy = str(orgin_agent_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{WORLD_NAME}/{self.worldview}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{WORLD_NAME}/{OUT_PUT_NPC_SYS_PROMPT}/{self.codename}_sys_prompt.md""")
        agentpy = agentpy.replace("<%GPT_MODEL>", self.gptmodel)
        agentpy = agentpy.replace("<%PORT>", str(self.port))
        agentpy = agentpy.replace("<%API>", self.api)
        self.agentpy = agentpy
        return self.agentpy

class TblStage:

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
        return f"TblStage({self.name}, {self.codename}, {self.description}, {self.gptmodel}, {self.port}, {self.api}, {self.worldview})"
        
    def isvalid(self) -> bool:
        return True
    
    def gen_sys_prompt(self, orgin_stage_template: str) -> str:
        stage_prompt = str(orgin_stage_template)
        stage_prompt = stage_prompt.replace("<%name>", self.name)
        stage_prompt = stage_prompt.replace("<%description>", self.description)
        self.sysprompt = stage_prompt
        return self.sysprompt
    
    def gen_agentpy(self, orgin_agent_template: str) -> str:
        agentpy = str(orgin_agent_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{WORLD_NAME}/{self.worldview}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{WORLD_NAME}/{OUT_PUT_STAGE_SYS_PROMPT}/{self.codename}_sys_prompt.md""")
        agentpy = agentpy.replace("<%GPT_MODEL>", self.gptmodel)
        agentpy = agentpy.replace("<%PORT>", str(self.port))
        agentpy = agentpy.replace("<%API>", self.api)
        self.agentpy = agentpy
        return self.agentpy
    

##全局的，方便，不封装了，反正当工具用
npc_sys_prompt_template = read_md(f"/{WORLD_NAME}/{NPC_SYS_PROMPT_TEMPLATE}")
stage_sys_prompt_template = read_md(f"/{WORLD_NAME}/{STAGE_SYS_PROMPT_TEMPLATE}")
gpt_agent_template = read_py(f"/{WORLD_NAME}/{GPT_AGENT_TEMPLATE}")
npcsheet = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='NPC', engine='openpyxl')
stagesheet = pd.read_excel(f"{WORLD_NAME}/{WORLD_NAME}.xlsx", sheet_name='Stage', engine='openpyxl')
tbl_npcs: list[TblNpc] = []
tbl_stages: list[TblStage] = []    
    
def gen_npcs() -> None:

    ## 读取Excel文件
    for index, row in npcsheet.iterrows():
        tblnpc = TblNpc(row["name"], row["codename"], row["description"], row["history"], row["GPT_MODEL"], row["PORT"], row["API"], RAG_FILE)
        if not tblnpc.isvalid():
            print(f"Invalid row: {tblnpc}")
            continue
        tblnpc.gen_sys_prompt(npc_sys_prompt_template)
        tblnpc.gen_agentpy(gpt_agent_template)
        tbl_npcs.append(tblnpc)

    for tblnpc in tbl_npcs:
        directory = f"{WORLD_NAME}/{OUT_PUT_NPC_SYS_PROMPT}"
        filename = f"{tblnpc.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblnpc.sysprompt)
            file.write("\n\n\n")

    for tblnpc in tbl_npcs:
        directory = f"{WORLD_NAME}/{OUT_PUT_AGENT}"
        filename = f"{tblnpc.codename}_agent.py"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblnpc.agentpy)
            file.write("\n\n\n")


def gen_stages() -> None:
   
    ## 读取Excel文件
    for index, row in stagesheet.iterrows():
        tblstage = TblStage(row["name"], row["codename"], row["description"], row["GPT_MODEL"], row["PORT"], row["API"], RAG_FILE)
        if not tblstage.isvalid():
            print(f"Invalid row: {tblstage}")
            continue
        tblstage.gen_sys_prompt(stage_sys_prompt_template)
        tblstage.gen_agentpy(gpt_agent_template)
        tbl_stages.append(tblstage)

    for tblstage in tbl_stages:
        directory = f"{WORLD_NAME}/{OUT_PUT_STAGE_SYS_PROMPT}"
        filename = f"{tblstage.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblstage.sysprompt)
            file.write("\n\n\n")

    for tblstage in tbl_stages:
        directory = f"{WORLD_NAME}/{OUT_PUT_AGENT}"
        filename = f"{tblstage.codename}_agent.py"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblstage.agentpy)
            file.write("\n\n\n")

def main() -> None:
    gen_npcs()
    gen_stages()

if __name__ == "__main__":
    main()
