import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import game_sample.configuration as configuration
import game_sample.utils
from typing import Any
from enum import StrEnum, unique


@unique
class DataWorldSystemProperty(StrEnum):
    NAME = "name"
    CODENAME = "codename"
    WORLD_SYSTEM_PROFILE = "world_system_profile"
    PORT = "PORT"
    API = "API"
    RAG = "RAG"
    SYS_PROMPT_TEMPLATE = "sys_prompt_template"
    AGENTPY_TEMPLATE = "agentpy_template"


############################################################################################################


class ExcelDataWorldSystem:

    def __init__(self, data: Any) -> None:
        assert data is not None
        self._data: Any = data
        self._gen_system_prompt: str = ""
        self._gen_agentpy: str = ""

    ############################################################################################################
    @property
    def name(self) -> str:
        return str(self._data[DataWorldSystemProperty.NAME])

    ############################################################################################################
    @property
    def codename(self) -> str:
        return str(self._data[DataWorldSystemProperty.CODENAME])

    ############################################################################################################
    @property
    def world_system_profile(self) -> str:
        return str(self._data[DataWorldSystemProperty.WORLD_SYSTEM_PROFILE])

    ############################################################################################################
    @property
    def port(self) -> int:
        return int(self._data[DataWorldSystemProperty.PORT])

    ############################################################################################################
    @property
    def api(self) -> str:
        return str(self._data[DataWorldSystemProperty.API])

    ############################################################################################################
    @property
    def rag(self) -> str:
        return str(self._data[DataWorldSystemProperty.RAG])

    ############################################################################################################
    @property
    def sys_prompt_template_path(self) -> str:
        return str(self._data[DataWorldSystemProperty.SYS_PROMPT_TEMPLATE])

    ############################################################################################################
    @property
    def agentpy_template_path(self) -> str:
        return str(self._data[DataWorldSystemProperty.AGENTPY_TEMPLATE])

    ############################################################################################################
    @property
    def localhost(self) -> str:
        return f"http://localhost:{self.port}{self.api}/"

    ############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        gen_prompt = str(sys_prompt_template)
        gen_prompt = gen_prompt.replace(
            configuration.SystemPromptReplaceSymbol.NAME, self.name
        )
        gen_prompt = gen_prompt.replace(
            configuration.SystemPromptReplaceSymbol.SYSTEM_PROMPT,
            self.world_system_profile,
        )
        self._gen_system_prompt = gen_prompt
        return self._gen_system_prompt

    ############################################################################################################
    def gen_agentpy(self, agent_py_template: str) -> str:
        gen_py = str(agent_py_template)
        gen_py = gen_py.replace(
            configuration.AgentAppReplaceSymbol.SYSTEM_PROMPT_CONTENT,
            self._gen_system_prompt,
        )

        gen_py = gen_py.replace(
            configuration.AgentAppReplaceSymbol.RAG_CONTENT,
            game_sample.utils.read_text_file(configuration.GAME_SAMPLE_DIR / self.rag),
        )
        gen_py = gen_py.replace(
            configuration.AgentAppReplaceSymbol.PORT, str(self.port)
        )
        gen_py = gen_py.replace(configuration.AgentAppReplaceSymbol.API, self.api)
        self._gen_agentpy = gen_py
        return self._gen_agentpy

    ############################################################################################################
    def write_sys_prompt(self) -> None:
        game_sample.utils.write_text_file(
            configuration.GAME_SAMPLE_OUT_PUT_WORLD_SYS_PROMPT_DIR,
            f"{self.codename}_sys_prompt.md",
            self._gen_system_prompt,
        )

    ############################################################################################################
    def write_agentpy(self) -> None:
        game_sample.utils.write_text_file(
            configuration.GAME_SAMPLE_OUT_PUT_AGENT_DIR,
            f"{self.codename}_agent.py",
            self._gen_agentpy,
        )


############################################################################################################
