import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import os
from loguru import logger
from typing import List
from budding_world.configuration import GAME_NAME, OUT_PUT_ACTOR_SYS_PROMPT_DIR, OUT_PUT_STAGE_SYS_PROMPT_DIR, OUT_PUT_AGENT_DIR


############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataActor:

    def __init__(self, name: str, 
                 codename: str, 
                 description: str, 
                 conversation_example: str,
                 #gptmodel: str, 
                 port: int, 
                 api: str, 
                 rag: str,
                 sys_prompt_template_path: str,
                 agentpy_template_path: str) -> None:
        
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.converation_example = conversation_example
        #self.gptmodel: str = gptmodel
        self.port: int = port
        self.api: str = api
        self._rag: str = rag
        self.mentioned_actors: List[str] = []
        self.mentioned_stages: List[str] = []
        self.mentioned_props: List[str] = []

        self.sysprompt: str = ""
        self.agentpy: str = ""
        logger.info(self.localhost_api())

        #self.attributes: str = attributes
        self._sys_prompt_template_path: str = sys_prompt_template_path
        self._agentpy_template_path = agentpy_template_path

    def __str__(self) -> str:
        return f"ExcelDataActor({self.name}, {self.codename})"
    
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        genprompt = str(sys_prompt_template)
        genprompt = genprompt.replace("<%name>", self.name)
        genprompt = genprompt.replace("<%description>", self.description)
        genprompt = genprompt.replace("<%conversation_example>", self.converation_example)
        self.sysprompt = genprompt
        return self.sysprompt
    
    def gen_agentpy(self, agent_py_template: str) -> str:
        agentpy = str(agent_py_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{GAME_NAME}/{self._rag}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{GAME_NAME}/{OUT_PUT_ACTOR_SYS_PROMPT_DIR}/{self.codename}_sys_prompt.md""")
        #agentpy = agentpy.replace("<%GPT_MODEL>", self.gptmodel)
        agentpy = agentpy.replace("<%PORT>", str(self.port))
        agentpy = agentpy.replace("<%API>", self.api)
        self.agentpy = agentpy
        return self.agentpy
    
    def localhost_api(self) -> str:
        return f"http://localhost:{self.port}{self.api}/"
    
    def write_sys_prompt(self) -> None: 
        try:
            directory = f"{GAME_NAME}/{OUT_PUT_ACTOR_SYS_PROMPT_DIR}"
            filename = f"{self.codename}_sys_prompt.md"
            path = os.path.join(directory, filename)
            # 确保目录存在
            os.makedirs(directory, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as file:
                file.write(self.sysprompt)
                file.write("\n\n\n")
        except Exception as e:
            logger.error(f"An error occurred: {e}") 

    def write_agentpy(self) -> None:
        try:
            directory = f"{GAME_NAME}/{OUT_PUT_AGENT_DIR}"
            filename = f"{self.codename}_agent.py"
            path = os.path.join(directory, filename)
            # 确保目录存在
            os.makedirs(directory, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as file:
                file.write(self.agentpy)
                file.write("\n\n\n")
        except Exception as e:
            logger.error(f"An error occurred: {e}") 

    def add_mentioned_actor(self, name: str) -> bool:
        if name == self.name:
            return False
        if name in self.mentioned_actors:
            return True
        if name in self.description:
            self.mentioned_actors.append(name)
            return True
        return False
    
    def add_mentioned_stage(self, stagename: str) -> bool:
        if stagename in self.mentioned_stages:
            return True
        if stagename in self.description:
            self.mentioned_stages.append(stagename)
            return True
        return False
    
    def check_mentioned_actor(self, name: str) -> bool:
        if name in self.mentioned_actors:
            return True
        return False
    
    def add_mentioned_prop(self, name: str) -> bool:
        if name in self.mentioned_props:
            return True
        if name in self.description:
            self.mentioned_props.append(name)
            return True
        return False
    
    def check_mentioned_prop(self, name: str) -> bool:
        if name in self.mentioned_props:
            return True
        return False
############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataStage:

    def __init__(self, name: str, 
                 codename: str, 
                 description: str, 
                 #gptmodel: str, 
                 port: int, 
                 api: str, 
                 rag: str, 
                 sys_prompt_template_path: str,
                 agentpy_template_path: str) -> None:
        
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        #self.gptmodel: str = gptmodel
        self.port: int = port
        self.api: str = api
        self._rag: str = rag

        self.sysprompt: str = ""
        self.agentpy: str = ""

        logger.info(self.localhost_api())
        #self.attributes: str = attributes

        self._sys_prompt_template_path: str = sys_prompt_template_path
        self._agentpy_template_path = agentpy_template_path

    def __str__(self) -> str:
        return f"ExcelDataStage({self.name}, {self.codename})"
    
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        genprompt = str(sys_prompt_template)
        genprompt = genprompt.replace("<%name>", self.name)
        genprompt = genprompt.replace("<%description>", self.description)
        self.sysprompt = genprompt
        return self.sysprompt
    
    def gen_agentpy(self, agent_py_template: str) -> str:
        agentpy = str(agent_py_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{GAME_NAME}/{self._rag}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{GAME_NAME}/{OUT_PUT_STAGE_SYS_PROMPT_DIR}/{self.codename}_sys_prompt.md""")
        #agentpy = agentpy.replace("<%GPT_MODEL>", self.gptmodel)
        agentpy = agentpy.replace("<%PORT>", str(self.port))
        agentpy = agentpy.replace("<%API>", self.api)
        self.agentpy = agentpy
        return self.agentpy
    
    def localhost_api(self) -> str:
        return f"http://localhost:{self.port}{self.api}/"
    
    def write_sys_prompt(self) -> None: 
        try:
            directory = f"{GAME_NAME}/{OUT_PUT_STAGE_SYS_PROMPT_DIR}"
            filename = f"{self.codename}_sys_prompt.md"
            path = os.path.join(directory, filename)
            # 确保目录存在
            os.makedirs(directory, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as file:
                file.write(self.sysprompt)
                file.write("\n\n\n")
        except Exception as e:
            logger.error(f"An error occurred: {e}") 

    def write_agentpy(self) -> None:
        try:
            directory = f"{GAME_NAME}/{OUT_PUT_AGENT_DIR}"
            filename = f"{self.codename}_agent.py"
            path = os.path.join(directory, filename)
            # 确保目录存在
            os.makedirs(directory, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as file:
                file.write(self.agentpy)
                file.write("\n\n\n")
        except Exception as e:
            logger.error(f"An error occurred: {e}") 
############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataProp:
    
    def __init__(self, name: str, codename: str, isunique: str, description: str, worldview: str, type: str, raw_attributes: str) -> None:
        self.name: str = name
        self.codename: str = codename
        self.description: str = description
        self.isunique: str = isunique
        self.worldview: str = worldview
        self.type: str = type

        ## 有些是nan。需要小心
        self.raw_attributes: str = raw_attributes
        if self.raw_attributes == "nan":
            self.raw_attributes = ""

    def __str__(self) -> str:
        return f"ExcelDataProp({self.name}, {self.codename}, {self.isunique}, {self.type}, {self.raw_attributes})"
