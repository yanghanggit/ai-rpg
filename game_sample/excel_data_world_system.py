import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from game_sample.configuration import (
    GAME_NAME,
    OUT_PUT_STAGE_SYS_PROMPT_DIR,
    OUT_PUT_AGENT_DIR,
)
import game_sample.utils
from typing import Any


class ExcelDataWorldSystem:

    def __init__(self, data: Any) -> None:
        self._data: Any = data
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
        gen_py = gen_py.replace(
            "<%SYS_PROMPT_MD_PATH>",
            f"""/{GAME_NAME}/{OUT_PUT_STAGE_SYS_PROMPT_DIR}/{self.codename}_sys_prompt.md""",
        )
        gen_py = gen_py.replace("<%PORT>", str(self.port))
        gen_py = gen_py.replace("<%API>", self.api)
        self._gen_agentpy = gen_py
        return self._gen_agentpy

    ############################################################################################################
    def write_sys_prompt(self) -> None:
        directory = Path(GAME_NAME) / OUT_PUT_STAGE_SYS_PROMPT_DIR
        game_sample.utils.write_text_file(
            directory, f"{self.codename}_sys_prompt.md", self._gen_sys_prompt
        )

    ############################################################################################################
    def write_agentpy(self) -> None:
        directory = Path(GAME_NAME) / OUT_PUT_AGENT_DIR
        game_sample.utils.write_text_file(
            directory, f"{self.codename}_agent.py", self._gen_agentpy
        )

    ############################################################################################################
    @property
    def gen_agentpy_path(self) -> Path:
        directory = Path(GAME_NAME) / OUT_PUT_AGENT_DIR
        return directory / f"{self.codename}_agent.py"


############################################################################################################
