import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
import game_sample.configuration
import game_sample.utils
from typing import Any, Final
from enum import StrEnum, unique


@unique
class DataStageProperty(StrEnum):
    NAME = "name"
    CODENAME = "codename"
    STAGE_PROFILE = "stage_profile"
    # PORT = "PORT"
    # API = "API"
    RAG = "RAG"
    SYS_PROMPT_TEMPLATE = "sys_prompt_template"
    AGENTPY_TEMPLATE = "agentpy_template"
    CONVERSATIONAL_STYLE = "conversational_style"
    TEMPERATURE = "temperature"


############################################################################################################
class ExcelDataStage:

    def __init__(self, data: Any) -> None:
        assert data is not None
        self._data = data
        self._gen_system_prompt: str = ""
        self._gen_agentpy: str = ""
        self._port: Final[int] = (
            game_sample.configuration.port_generator.gen_stage_port()
        )

    ############################################################################################################
    @property
    def name(self) -> str:
        return str(self._data[DataStageProperty.NAME])

    ############################################################################################################
    @property
    def codename(self) -> str:
        return str(self._data[DataStageProperty.CODENAME])

    ############################################################################################################
    @property
    def stage_profile(self) -> str:
        return str(self._data[DataStageProperty.STAGE_PROFILE])

    ############################################################################################################
    @property
    def port(self) -> int:
        return self._port
        # return int(self._data[DataStageProperty.PORT])

    ############################################################################################################
    @property
    def api_path(self) -> str:
        assert self.codename != "", "codename must not be empty."
        return f"/stage/{self.codename}"

        # assert self.codename in str(
        #     self._data[DataStageProperty.API]
        # ), "API must contain codename."
        # return str(self._data[DataStageProperty.API])

    ############################################################################################################
    @property
    def rag(self) -> str:
        return str(self._data[DataStageProperty.RAG])

    ############################################################################################################
    @property
    def sys_prompt_template_path(self) -> str:
        return str(self._data[DataStageProperty.SYS_PROMPT_TEMPLATE])

    ############################################################################################################
    @property
    def agentpy_template_path(self) -> str:
        return str(self._data[DataStageProperty.AGENTPY_TEMPLATE])

    ############################################################################################################
    @property
    def conversational_style(self) -> str:
        return str(self._data[DataStageProperty.CONVERSATIONAL_STYLE])

    ############################################################################################################
    @property
    def localhost_api_url(self) -> str:
        return f"http://localhost:{self.port}{self.api_path}/"

    ############################################################################################################
    @property
    def temperature(self) -> float:
        if self._data[DataStageProperty.TEMPERATURE] is not None:
            return 0.7
        return float(self._data[DataStageProperty.TEMPERATURE])

    ############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        gen_prompt = str(sys_prompt_template)
        gen_prompt = gen_prompt.replace(
            game_sample.configuration.SystemPromptReplaceSymbol.NAME, self.name
        )
        gen_prompt = gen_prompt.replace(
            game_sample.configuration.SystemPromptReplaceSymbol.SYSTEM_PROMPT,
            self.stage_profile,
        )
        gen_prompt = gen_prompt.replace(
            game_sample.configuration.SystemPromptReplaceSymbol.CONVERSATIONAL_STYLE,
            self.conversational_style,
        )
        self._gen_system_prompt = gen_prompt
        return self._gen_system_prompt

    ############################################################################################################
    def gen_agentpy(self, agent_py_template: str) -> str:
        gen_py = str(agent_py_template)
        gen_py = gen_py.replace(
            game_sample.configuration.AgentAppReplaceSymbol.SYSTEM_PROMPT_CONTENT,
            self._gen_system_prompt,
        )

        gen_py = gen_py.replace(
            game_sample.configuration.AgentAppReplaceSymbol.RAG_CONTENT,
            game_sample.utils.read_text_file(
                game_sample.configuration.GAME_SAMPLE_DIR / self.rag
            ),
        )
        gen_py = gen_py.replace(
            game_sample.configuration.AgentAppReplaceSymbol.PORT, str(self.port)
        )
        gen_py = gen_py.replace(
            game_sample.configuration.AgentAppReplaceSymbol.API, self.api_path
        )
        gen_py = gen_py.replace(
            game_sample.configuration.AgentAppReplaceSymbol.TEMPERATURE,
            str(self.temperature),
        )

        self._gen_agentpy = gen_py
        return self._gen_agentpy

    ############################################################################################################
    def write_sys_prompt(self) -> None:
        game_sample.utils.write_text_file(
            game_sample.configuration.GAME_SAMPLE_OUT_PUT_STAGE_SYS_PROMPT_DIR,
            f"{self.codename}_sys_prompt.md",
            self._gen_system_prompt,
        )

    ############################################################################################################
    def write_agentpy(self) -> None:
        game_sample.utils.write_text_file(
            game_sample.configuration.GAME_SAMPLE_OUT_PUT_AGENT_DIR,
            f"{self.codename}_agent.py",
            self._gen_agentpy,
        )

    ############################################################################################################
