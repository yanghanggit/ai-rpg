import pandas as pd
from auxiliary.extract_md_content import extract_md_content
import os
from loguru import logger
from typing import Any
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


class TblNpc:

    def __init__(self, name: str, codename: str, description: str, history: str) -> None:
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.history: str = history
        self.sysprompt: str = ""

    def __str__(self) -> str:
        return f"TblNpc({self.name}, {self.codename}, {self.description}, {self.history})"
        
    def isvalid(self) -> bool:
        return self.name and self.codename and self.description and self.history
    
    def gen_sys_prompt(self, orgin_npc_template: str) -> str:
        npc_prompt = str(orgin_npc_template)
        npc_prompt = npc_prompt.replace("<%name>", self.name)
        npc_prompt = npc_prompt.replace("<%description>", self.description)
        npc_prompt = npc_prompt.replace("<%history>", self.history)
        self.sysprompt = npc_prompt
        return self.sysprompt

class TblStage:

    def __init__(self, name: str, codename: str, description: str) -> None:
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.sysprompt: str = ""

    def __str__(self) -> str:
        return f"TblStage({self.name}, {self.codename}, {self.description})"
        
    def isvalid(self) -> bool:
        return self.name and self.codename and self.description
    
    def gen_sys_prompt(self, orgin_stage_template: str) -> str:
        stage_prompt = str(orgin_stage_template)
        stage_prompt = stage_prompt.replace("<%name>", self.name)
        stage_prompt = stage_prompt.replace("<%description>", self.description)
        self.sysprompt = stage_prompt
        return self.sysprompt



def gen_npc_sys_prompt() -> None:
    ## 读取md文件
    orgin_npc_template = read_md("/budding_world/npc_sys_prompt_template.md")
    #print(orgin_npc_template)
    #print("________________________________________________________________________")

    # 读取xlsx文件
    df = pd.read_excel('budding_world/budding_world.xlsx',  sheet_name='NPC', engine='openpyxl')
    #print(df)
    # 将DataFrame转换为JSON，禁用ASCII强制转换
    json_data: DataFrame = df.to_json(orient='records', force_ascii=False)
    #print(json_data)
    #print("________________________________________________________________________")

    gen_tbl_npc: list[TblNpc] = []
    ## 读取Excel文件
    for index, row in df.iterrows():
        tblnpc = TblNpc(row["name"], row["codename"], row["description"], row["history"])
        if not tblnpc.isvalid():
            print(f"Invalid row: {tblnpc}")
            continue

        tblnpc.gen_sys_prompt(orgin_npc_template)
        gen_tbl_npc.append(tblnpc)
    print("________________________________________________________________________")

    for tblnpc in gen_tbl_npc:
        directory = f"budding_world/gen_npc_sys_prompt"
        filename = f"{tblnpc.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)

        # 确保目录存在
        os.makedirs(directory, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblnpc.sysprompt)
            file.write("\n\n\n")
    
    print("________________________________________________________________________")




def gen_stage_sys_prompt() -> None:
    ## 读取md文件
    orgin_stage_template = read_md("/budding_world/stage_sys_prompt_template.md")
    #print(orgin_stage_template)
    #print("________________________________________________________________________")

    # 读取xlsx文件
    df = pd.read_excel('budding_world/budding_world.xlsx', sheet_name='Stage', engine='openpyxl')
    #print(df)
    # 将DataFrame转换为JSON，禁用ASCII强制转换
    json_data: DataFrame = df.to_json(orient='records', force_ascii=False)
    #print(json_data)
    #print("________________________________________________________________________")

    gen_tbl_stage: list[TblStage] = []
    ## 读取Excel文件
    for index, row in df.iterrows():
        tblstage = TblStage(row["name"], row["codename"], row["description"])
        if not tblstage.isvalid():
            print(f"Invalid row: {tblstage}")
            continue

        tblstage.gen_sys_prompt(orgin_stage_template)
        gen_tbl_stage.append(tblstage)
    print("________________________________________________________________________")

    for tblstage in gen_tbl_stage:
        directory = f"budding_world/gen_stage_sys_prompt"
        filename = f"{tblstage.codename}_sys_prompt.md"
        path = os.path.join(directory, filename)

        # 确保目录存在
        os.makedirs(directory, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as file:
            file.write(tblstage.sysprompt)
            file.write("\n\n\n")
    
    print("________________________________________________________________________")



def gen_npc_agents() -> None:
    with open("budding_world/gpt_agent_template.py", 'r', encoding='utf-8') as file:
        agent_template = file.read()


        agentpy = str(agent_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", "/story/world_view.md")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", "/actor/npc/thief.md")
        agentpy = agentpy.replace("<%GPT_MODEL>", "gpt-4-turbo-preview")
        agentpy = agentpy.replace("<%PORT>", "8026")
        agentpy = agentpy.replace("<%API>", "/actor/npc/thief/")
    
        print(agentpy)

        directory = f"budding_world/gen_agent"
        filename = f"test_agent.py"
        path = os.path.join(directory, filename)

        # 确保目录存在
        os.makedirs(directory, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as file:
            file.write(agentpy)
            file.write("\n\n\n")





def main() -> None:
    #print("Hello, World!")

    try:
        #gen_npc_sys_prompt()

        #gen_stage_sys_prompt()

        gen_npc_agents()
       

       

       

    



        #print("________________________________________________________________________")

    except Exception as e:
        print("==> ", e)
        #logger.exception(e)
        return

if __name__ == "__main__":
    main()
