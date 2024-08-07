import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List
from game_sample.configuration import GAME_NAME, OUT_PUT_ACTOR_SYS_PROMPT_DIR, OUT_PUT_STAGE_SYS_PROMPT_DIR, OUT_PUT_AGENT_DIR
from game_sample.utils import write_text_file
from typing import Any

############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataActor:

    def __init__(self, data: Any) -> None:
        self._data = data
  
        # 构建出来的数据
        self._gen_system_prompt: str = ""
        self._gen_agentpy: str = ""
        self._actor_archives: List[str] = []
        self._stage_archives: List[str] = []
        self._prop_archives: List[str] = []
############################################################################################################
    @property
    def name(self) -> str:
        return str(self._data["name"])
    
    @property
    def codename(self) -> str:
        return str(self._data["codename"])
    
    @property
    def description(self) -> str:
        return str(self._data["description"])
    
    @property
    def conversation_example(self) -> str:
        return str(self._data["conversation_example"])
    
    @property
    def port(self) -> int:
        return int(self._data["PORT"])
    
    @property
    def api(self) -> str:
        return str(self._data["API"])
    
    @property
    def rag(self) -> str:
        return str(self._data["RAG"])
    
    @property
    def sys_prompt_template_path(self) -> str:
        return str(self._data["sys_prompt_template"])
    

    @property
    def agentpy_template_path(self) -> str:
        return str(self._data["agentpy_template"])

    @property
    def body(self) -> str:
        return str(self._data["body"])
############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        gen_prompt = str(sys_prompt_template)
        gen_prompt = gen_prompt.replace("<%name>", self.name)
        gen_prompt = gen_prompt.replace("<%description>", self.description)
        gen_prompt = gen_prompt.replace("<%conversation_example>", self.conversation_example)
        self._gen_system_prompt = gen_prompt
        return self._gen_system_prompt
############################################################################################################
    def gen_agentpy(self, agent_py_template: str) -> str:
        gen_py = str(agent_py_template)
        gen_py = gen_py.replace("<%RAG_MD_PATH>", f"""/{GAME_NAME}/{self.rag}""")
        gen_py = gen_py.replace("<%SYS_PROMPT_MD_PATH>", f"""/{GAME_NAME}/{OUT_PUT_ACTOR_SYS_PROMPT_DIR}/{self.codename}_sys_prompt.md""")
        gen_py = gen_py.replace("<%PORT>", str(self.port))
        gen_py = gen_py.replace("<%API>", self.api)
        self._gen_agentpy = gen_py
        return self._gen_agentpy
############################################################################################################
    @property
    def localhost(self) -> str:
        return f"http://localhost:{self.port}{self.api}/"
############################################################################################################
    def write_sys_prompt(self) -> None: 
        directory = Path(GAME_NAME) / OUT_PUT_ACTOR_SYS_PROMPT_DIR
        write_text_file(directory, f"{self.codename}_sys_prompt.md", self._gen_system_prompt)
############################################################################################################
    def write_agentpy(self) -> None:
        directory = Path(GAME_NAME) / OUT_PUT_AGENT_DIR
        write_text_file(directory, f"{self.codename}_agent.py", self._gen_agentpy)
############################################################################################################
    def add_actor_archive(self, actor_name: str) -> bool:

        if actor_name == self.name:
            return False
        
        if actor_name in self._actor_archives:
            return True
        
        if actor_name in self.description:
            self._actor_archives.append(actor_name)
            return True
        
        return False
############################################################################################################
    def add_stage_archive(self, stage_name: str) -> bool:

        if stage_name in self._stage_archives:
            return True
        
        if stage_name in self.description:
            self._stage_archives.append(stage_name)
            return True
        
        return False
############################################################################################################
    def check_actor_archive(self, actor_name: str) -> bool:
        return actor_name in self._actor_archives
############################################################################################################
    def add_prop_archive(self, prop_name: str) -> bool:

        if prop_name in self._prop_archives:
            return True
        
        if prop_name in self.description:
            self._prop_archives.append(prop_name)
            return True
        
        return False
############################################################################################################
    def check_prop_archive(self, prop_name: str) -> bool:
        return prop_name in self._prop_archives
############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataStage:

    def __init__(self, data: Any) -> None:
        self._data = data
        self._gen_system_prompt: str = ""
        self._gen_agentpy: str = ""

    @property
    def name(self) -> str:
        return str(self._data["name"])
    
    @property
    def codename(self) -> str:
        return str(self._data["codename"])
    
    @property
    def description(self) -> str:
        return str(self._data["description"])
    
    @property
    def port(self) -> int:
        return int(self._data["PORT"])
    
    @property
    def api(self) -> str:
        return str(self._data["API"])
    
    @property
    def rag(self) -> str:
        return str(self._data["RAG"])
    

    @property
    def sys_prompt_template_path(self) -> str:
        return str(self._data["sys_prompt_template"])
    

    @property
    def agentpy_template_path(self) -> str:
        return str(self._data["agentpy_template"])


    @property
    def localhost(self) -> str:
        return f"http://localhost:{self.port}{self.api}/"
############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        gen_prompt = str(sys_prompt_template)
        gen_prompt = gen_prompt.replace("<%name>", self.name)
        gen_prompt = gen_prompt.replace("<%description>", self.description)
        self._gen_system_prompt = gen_prompt
        return self._gen_system_prompt
############################################################################################################
    def gen_agentpy(self, agent_py_template: str) -> str:
        gen_py = str(agent_py_template)
        gen_py = gen_py.replace("<%RAG_MD_PATH>", f"""/{GAME_NAME}/{self.rag}""")
        gen_py = gen_py.replace("<%SYS_PROMPT_MD_PATH>", f"""/{GAME_NAME}/{OUT_PUT_STAGE_SYS_PROMPT_DIR}/{self.codename}_sys_prompt.md""")
        gen_py = gen_py.replace("<%PORT>", str(self.port))
        gen_py = gen_py.replace("<%API>", self.api)
        self._gen_agentpy = gen_py
        return self._gen_agentpy   
############################################################################################################
    def write_sys_prompt(self) -> None: 
        directory = Path(GAME_NAME) / OUT_PUT_STAGE_SYS_PROMPT_DIR
        write_text_file(directory, f"{self.codename}_sys_prompt.md", self._gen_system_prompt)
############################################################################################################
    def write_agentpy(self) -> None:
        directory = Path(GAME_NAME) / OUT_PUT_AGENT_DIR
        write_text_file(directory, f"{self.codename}_agent.py", self._gen_agentpy)
############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataProp:

    def __init__(self, data: Any) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return str(self._data["name"])
    
    @property
    def codename(self) -> str:
        return str(self._data["codename"])
    
    @property
    def description(self) -> str:
        return str(self._data["description"])
    
    @property
    def isunique(self) -> str:
        return str(self._data["isunique"])
    
    @property
    def rag(self) -> str:
        return str(self._data["RAG"])
    
    @property
    def type(self) -> str:
        return str(self._data["type"])
    
    @property
    def attributes(self) -> str:
        return str(self._data["attributes"])
    
    @property
    def appearance(self) -> str:
        return str(self._data["appearance"])
############################################################################################################
############################################################################################################
############################################################################################################
class ExcelDataWorldSystem:

    def __init__(self, data: Any) -> None:
        self._data = data
        self._gen_sys_prompt: str = ""
        self._gen_agentpy: str = ""

    @property
    def name(self) -> str:
        return str(self._data["name"])
    
    @property
    def codename(self) -> str:
        return str(self._data["codename"])
    
    @property
    def description(self) -> str:
        return str(self._data["description"])
    
    @property
    def port(self) -> int:
        return int(self._data["PORT"])
    
    @property
    def api(self) -> str:
        return str(self._data["API"])
    
    @property
    def rag(self) -> str:
        return str(self._data["RAG"])
    
    @property
    def sys_prompt_template_path(self) -> str:
        return str(self._data["sys_prompt_template"])
    
    @property
    def agentpy_template_path(self) -> str:
        return str(self._data["agentpy_template"])


############################################################################################################
    @property
    def localhost(self) -> str:
        return f"http://localhost:{self.port}{self.api}/"
############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        gen_prompt = str(sys_prompt_template)
        gen_prompt = gen_prompt.replace("<%name>", self.name)
        gen_prompt = gen_prompt.replace("<%description>", self.description)
        self._gen_sys_prompt = gen_prompt
        return self._gen_sys_prompt
############################################################################################################
    def gen_agentpy(self, agent_py_template: str) -> str:
        gen_py = str(agent_py_template)
        gen_py = gen_py.replace("<%RAG_MD_PATH>", f"""/{GAME_NAME}/{self.rag}""")
        gen_py = gen_py.replace("<%SYS_PROMPT_MD_PATH>", f"""/{GAME_NAME}/{OUT_PUT_STAGE_SYS_PROMPT_DIR}/{self.codename}_sys_prompt.md""")
        gen_py = gen_py.replace("<%PORT>", str(self.port))
        gen_py = gen_py.replace("<%API>", self.api)
        self._gen_agentpy = gen_py
        return self._gen_agentpy
############################################################################################################
    def write_sys_prompt(self) -> None: 
        directory = Path(GAME_NAME) / OUT_PUT_STAGE_SYS_PROMPT_DIR
        write_text_file(directory, f"{self.codename}_sys_prompt.md", self._gen_sys_prompt)
############################################################################################################
    def write_agentpy(self) -> None:
        directory = Path(GAME_NAME) / OUT_PUT_AGENT_DIR
        write_text_file(directory, f"{self.codename}_agent.py", self._gen_agentpy)
############################################################################################################