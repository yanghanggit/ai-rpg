import pandas as pd
#from auxiliary.extract_md_content import extract_md_content
import os
from loguru import logger
#from typing import Any
from pandas import DataFrame


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
    
    def gen_agentpy(self, orgin_agent_template: str, path: str) -> str:
        agentpy = str(orgin_agent_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""{path}/{self.worldview}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""{path}/gen_npc_sys_prompt/{self.codename}_sys_prompt.md""")
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
    
    def gen_agentpy(self, orgin_agent_template: str, path: str) -> str:
        agentpy = str(orgin_agent_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""{path}/{self.worldview}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""{path}/gen_npc_sys_prompt/{self.codename}_sys_prompt.md""")
        agentpy = agentpy.replace("<%GPT_MODEL>", self.gptmodel)
        agentpy = agentpy.replace("<%PORT>", str(self.port))
        agentpy = agentpy.replace("<%API>", self.api)
        self.agentpy = agentpy
        return self.agentpy
    

def gen_npcs() -> None:
    ## 读取md文件
    orgin_npc_template = read_md("/budding_world/npc_sys_prompt_template.md")
    orgin_agent_template = read_py("/budding_world/gpt_agent_template.py")
    # 读取xlsx文件
    df = pd.read_excel('budding_world/budding_world.xlsx',  sheet_name='NPC', engine='openpyxl')
    # 将DataFrame转换为JSON，禁用ASCII强制转换
    #json_data: DataFrame = df.to_json(orient='records', force_ascii=False)

    gen_tbl_npc: list[TblNpc] = []
    ## 读取Excel文件
    for index, row in df.iterrows():
        tblnpc = TblNpc(row["name"], row["codename"], row["description"], row["history"], row["GPT_MODEL"], row["PORT"], row["API"], "rag.md")
        if not tblnpc.isvalid():
            print(f"Invalid row: {tblnpc}")
            continue
        tblnpc.gen_sys_prompt(orgin_npc_template)
        tblnpc.gen_agentpy(orgin_agent_template, "/budding_world")
        gen_tbl_npc.append(tblnpc)

    for tblnpc in gen_tbl_npc:
        directory = f"budding_world/gen_npc_sys_prompt"
        filename = f"{tblnpc.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblnpc.sysprompt)
            file.write("\n\n\n")

    for tblnpc in gen_tbl_npc:
        directory = f"budding_world/gen_agent"
        filename = f"{tblnpc.codename}_agent.py"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblnpc.agentpy)
            file.write("\n\n\n")


def gen_stages() -> None:
    ## 读取md文件
    orgin_stage_template = read_md("/budding_world/stage_sys_prompt_template.md")
    orgin_agent_template = read_py("/budding_world/gpt_agent_template.py")
    # 读取xlsx文件
    df = pd.read_excel('budding_world/budding_world.xlsx', sheet_name='Stage', engine='openpyxl')
    # 将DataFrame转换为JSON，禁用ASCII强制转换
    #json_data: DataFrame = df.to_json(orient='records', force_ascii=False)

    gen_tbl_stage: list[TblStage] = []
    ## 读取Excel文件
    for index, row in df.iterrows():
        tblstage = TblStage(row["name"], row["codename"], row["description"], row["GPT_MODEL"], row["PORT"], row["API"], "rag.md")
        if not tblstage.isvalid():
            print(f"Invalid row: {tblstage}")
            continue
        tblstage.gen_sys_prompt(orgin_stage_template)
        tblstage.gen_agentpy(orgin_agent_template, "/budding_world")
        gen_tbl_stage.append(tblstage)

    for tblstage in gen_tbl_stage:
        directory = f"budding_world/gen_stage_sys_prompt"
        filename = f"{tblstage.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblstage.sysprompt)
            file.write("\n\n\n")

    for tblstage in gen_tbl_stage:
        directory = f"budding_world/gen_agent"
        filename = f"{tblstage.codename}_agent.py"
        path = os.path.join(directory, filename)
        # 确保目录存在
        os.makedirs(directory, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblstage.agentpy)
            file.write("\n\n\n")

def main() -> None:
    try:
        gen_npcs()
        gen_stages()
    except Exception as e:
        logger.exception(e)
        return

if __name__ == "__main__":
    main()
