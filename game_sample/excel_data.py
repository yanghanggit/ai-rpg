import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import List
from game_sample.configuration import GAME_NAME, OUT_PUT_ACTOR_SYS_PROMPT_DIR, OUT_PUT_STAGE_SYS_PROMPT_DIR, OUT_PUT_AGENT_DIR
from game_sample.utils import write_text_file


############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataActor:

    def __init__(self, name: str, 
                 codename: str, 
                 description: str, 
                 conversation_example: str,
                 port: int, 
                 api: str, 
                 rag: str,
                 sys_prompt_template_path: str,
                 agentpy_template_path: str,
                 body: str) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._description: str = description
        self._converation_example: str = conversation_example
        self._port: int = port
        self._api: str = api
        logger.info(self.localhost())
        self._rag: str = rag
        self._actor_archives: List[str] = []
        self._stage_archives: List[str] = []
        self._prop_archives: List[str] = []
        self._system_prompt: str = ""
        self._agentpy: str = ""
        self._sys_prompt_template_path: str = sys_prompt_template_path
        self._agentpy_template_path: str = agentpy_template_path
        self._body: str = body
############################################################################################################
    def __str__(self) -> str:
        return f"ExcelDataActor({self._name}, {self._codename})"
############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        genprompt = str(sys_prompt_template)
        genprompt = genprompt.replace("<%name>", self._name)
        genprompt = genprompt.replace("<%description>", self._description)
        genprompt = genprompt.replace("<%conversation_example>", self._converation_example)
        self._system_prompt = genprompt
        return self._system_prompt
############################################################################################################
    def gen_agentpy(self, agent_py_template: str) -> str:
        agentpy = str(agent_py_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{GAME_NAME}/{self._rag}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{GAME_NAME}/{OUT_PUT_ACTOR_SYS_PROMPT_DIR}/{self._codename}_sys_prompt.md""")
        agentpy = agentpy.replace("<%PORT>", str(self._port))
        agentpy = agentpy.replace("<%API>", self._api)
        self._agentpy = agentpy
        return self._agentpy
############################################################################################################
    def localhost(self) -> str:
        return f"http://localhost:{self._port}{self._api}/"
############################################################################################################
    def write_sys_prompt(self) -> None: 
        directory = Path(GAME_NAME) / OUT_PUT_ACTOR_SYS_PROMPT_DIR
        write_text_file(directory, f"{self._codename}_sys_prompt.md", self._system_prompt)
############################################################################################################
    def write_agentpy(self) -> None:
        directory = Path(GAME_NAME) / OUT_PUT_AGENT_DIR
        write_text_file(directory, f"{self._codename}_agent.py", self._agentpy)
############################################################################################################
    def add_actor_archive(self, name: str) -> bool:
        if name == self._name:
            return False
        if name in self._actor_archives:
            return True
        if name in self._description:
            self._actor_archives.append(name)
            return True
        return False
############################################################################################################
    def add_stage_archive(self, stagename: str) -> bool:
        if stagename in self._stage_archives:
            return True
        if stagename in self._description:
            self._stage_archives.append(stagename)
            return True
        return False
############################################################################################################
    def check_actor_archive(self, name: str) -> bool:
        return name in self._actor_archives
############################################################################################################
    def add_prop_archive(self, name: str) -> bool:
        if name in self._prop_archives:
            return True
        if name in self._description:
            self._prop_archives.append(name)
            return True
        return False
############################################################################################################
    def check_prop_archive(self, name: str) -> bool:
        return name in self._prop_archives
############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataStage:

    def __init__(self, 
                 name: str, 
                 codename: str, 
                 description: str, 
                 port: int, 
                 api: str, 
                 rag: str, 
                 sys_prompt_template_path: str,
                 agentpy_template_path: str) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._description: str = description
        self._port: int = port
        self._api: str = api
        logger.info(self.localhost())
        self._rag: str = rag
        self._system_prompt: str = ""
        self._agentpy: str = ""
        self._sys_prompt_template_path: str = sys_prompt_template_path
        self._agentpy_template_path: str = agentpy_template_path
############################################################################################################
    def __str__(self) -> str:
        return f"ExcelDataStage({self._name}, {self._codename})"
############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        genprompt = str(sys_prompt_template)
        genprompt = genprompt.replace("<%name>", self._name)
        genprompt = genprompt.replace("<%description>", self._description)
        self._system_prompt = genprompt
        return self._system_prompt
############################################################################################################
    def gen_agentpy(self, agent_py_template: str) -> str:
        agentpy = str(agent_py_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{GAME_NAME}/{self._rag}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{GAME_NAME}/{OUT_PUT_STAGE_SYS_PROMPT_DIR}/{self._codename}_sys_prompt.md""")
        agentpy = agentpy.replace("<%PORT>", str(self._port))
        agentpy = agentpy.replace("<%API>", self._api)
        self._agentpy = agentpy
        return self._agentpy
############################################################################################################
    def localhost(self) -> str:
        return f"http://localhost:{self._port}{self._api}/"
############################################################################################################
    def write_sys_prompt(self) -> None: 
        directory = Path(GAME_NAME) / OUT_PUT_STAGE_SYS_PROMPT_DIR
        write_text_file(directory, f"{self._codename}_sys_prompt.md", self._system_prompt)
############################################################################################################
    def write_agentpy(self) -> None:
        directory = Path(GAME_NAME) / OUT_PUT_AGENT_DIR
        write_text_file(directory, f"{self._codename}_agent.py", self._agentpy)
############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataProp:
    
    def __init__(self, name: str, codename: str, isunique: str, description: str, rag: str, type: str, attributes: str) -> None:
        self._name: str = name
        self._codename: str = codename
        self._description: str = description
        self._isunique: str = isunique
        self._rag: str = rag
        self._type: str = type
        self._attributes: str = attributes
############################################################################################################
    def __str__(self) -> str:
        return f"ExcelDataProp({self._name}, {self._codename}, {self._isunique}, {self._type}, {self._attributes})"
############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataWorldSystem:

    def __init__(self, 
                 name: str, 
                 codename: str, 
                 description: str, 
                 port: int, 
                 api: str, 
                 rag: str, 
                 sys_prompt_template_path: str,
                 agentpy_template_path: str) -> None:
        
        self._name: str = name
        self._codename: str = codename
        self._description: str = description
        self._port: int = port
        self._api: str = api
        logger.info(self.localhost())
        self._rag: str = rag
        self._sysprompt: str = ""
        self._agentpy: str = ""
        self._sys_prompt_template_path: str = sys_prompt_template_path
        self._agentpy_template_path: str = agentpy_template_path
############################################################################################################
    def __str__(self) -> str:
        return f"ExcelDataWorldSystem({self._name}, {self._codename})"
############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        genprompt = str(sys_prompt_template)
        genprompt = genprompt.replace("<%name>", self._name)
        genprompt = genprompt.replace("<%description>", self._description)
        self._sysprompt = genprompt
        return self._sysprompt
############################################################################################################
    def gen_agentpy(self, agent_py_template: str) -> str:
        agentpy = str(agent_py_template)
        agentpy = agentpy.replace("<%RAG_MD_PATH>", f"""/{GAME_NAME}/{self._rag}""")
        agentpy = agentpy.replace("<%SYS_PROMPT_MD_PATH>", f"""/{GAME_NAME}/{OUT_PUT_STAGE_SYS_PROMPT_DIR}/{self._codename}_sys_prompt.md""")
        agentpy = agentpy.replace("<%PORT>", str(self._port))
        agentpy = agentpy.replace("<%API>", self._api)
        self._agentpy = agentpy
        return self._agentpy
############################################################################################################
    def localhost(self) -> str:
        return f"http://localhost:{self._port}{self._api}/"
############################################################################################################
    def write_sys_prompt(self) -> None: 
        directory = Path(GAME_NAME) / OUT_PUT_STAGE_SYS_PROMPT_DIR
        write_text_file(directory, f"{self._codename}_sys_prompt.md", self._sysprompt)
############################################################################################################
    def write_agentpy(self) -> None:
        directory = Path(GAME_NAME) / OUT_PUT_AGENT_DIR
        write_text_file(directory, f"{self._codename}_agent.py", self._agentpy)
############################################################################################################