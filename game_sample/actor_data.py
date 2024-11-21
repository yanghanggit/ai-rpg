import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import Final, List, Any
import game_sample.utils
from enum import StrEnum, unique
import game_sample.configuration


@unique
class DataActorProperty(StrEnum):
    NAME = "name"
    CODENAME = "codename"
    ACTOR_PROFILE = "actor_profile"
    CONVERSATIONAL_STYLE = "conversational_style"
    RAG = "RAG"
    SYS_PROMPT_TEMPLATE = "sys_prompt_template"
    AGENTPY_TEMPLATE = "agentpy_template"
    BASE_FORM = "base_form"
    TEMPERATURE = "temperature"


############################################################################################################


class ExcelDataActor:

    def __init__(self, data: Any) -> None:
        assert data is not None
        self._data = data

        # 构建出来的数据
        self._gen_system_prompt: str = ""
        self._gen_agentpy: str = ""
        self._actor_archives: List[str] = []
        self._stage_archives: List[str] = []
        self._prop_archives: List[str] = []
        self._port: Final[int] = (
            game_sample.configuration.port_generator.gen_actor_port()
        )

    ############################################################################################################
    @property
    def name(self) -> str:
        return str(self._data[DataActorProperty.NAME])

    ############################################################################################################
    @property
    def codename(self) -> str:
        return str(self._data[DataActorProperty.CODENAME])

    ############################################################################################################
    @property
    def actor_profile(self) -> str:
        return str(self._data[DataActorProperty.ACTOR_PROFILE])

    ############################################################################################################
    @property
    def conversational_style(self) -> str:
        return str(self._data[DataActorProperty.CONVERSATIONAL_STYLE])

    ############################################################################################################
    @property
    def port(self) -> int:
        return self._port

    ############################################################################################################
    @property
    def api_path(self) -> str:
        assert self.codename != ""
        assert "/" not in self.codename
        return f"/actor/{self.codename}"

    ############################################################################################################
    @property
    def rag(self) -> str:
        return str(self._data[DataActorProperty.RAG])

    ############################################################################################################
    @property
    def sys_prompt_template_path(self) -> str:
        return str(self._data[DataActorProperty.SYS_PROMPT_TEMPLATE])

    ############################################################################################################
    @property
    def agentpy_template_path(self) -> str:
        return str(self._data[DataActorProperty.AGENTPY_TEMPLATE])

    ############################################################################################################
    @property
    def base_form(self) -> str:
        assert str(self._data[DataActorProperty.BASE_FORM]) != ""
        assert "#" not in str(self._data[DataActorProperty.BASE_FORM])
        return str(self._data[DataActorProperty.BASE_FORM])

    ############################################################################################################
    @property
    def localhost_api_url(self) -> str:
        return f"http://localhost:{self.port}{self.api_path}/"

    ############################################################################################################
    @property
    def temperature(self) -> float:
        if self._data[DataActorProperty.TEMPERATURE] is None:
            return 0.7
        return float(self._data[DataActorProperty.TEMPERATURE])

    ############################################################################################################
    def gen_sys_prompt(self, sys_prompt_template: str) -> str:
        gen_prompt = str(sys_prompt_template)
        gen_prompt = gen_prompt.replace(
            game_sample.configuration.SystemPromptReplaceSymbol.NAME, self.name
        )
        gen_prompt = gen_prompt.replace(
            game_sample.configuration.SystemPromptReplaceSymbol.SYSTEM_PROMPT,
            self.actor_profile,
        )
        gen_prompt = gen_prompt.replace(
            game_sample.configuration.SystemPromptReplaceSymbol.BASE_FORM,
            self.base_form,
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
            game_sample.configuration.GAME_SAMPLE_OUT_PUT_ACTOR_SYS_PROMPT_DIR,
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
    def add_actor_archive(self, actor_name: str) -> bool:

        if actor_name == self.name:
            return False

        if actor_name in self._actor_archives:
            return True

        if actor_name in self.actor_profile:
            self._actor_archives.append(actor_name)
            return True

        return False

    ############################################################################################################
    def add_stage_archive(self, stage_name: str) -> bool:

        if stage_name in self._stage_archives:
            return True

        if stage_name in self.actor_profile:
            self._stage_archives.append(stage_name)
            return True

        return False

    ############################################################################################################
    def has_actor_in_archives(self, actor_name: str) -> bool:
        return actor_name in self._actor_archives

    ############################################################################################################
    def add_prop_archive(self, prop_name: str) -> bool:

        if prop_name in self._prop_archives:
            return True

        if prop_name in self.actor_profile:
            self._prop_archives.append(prop_name)
            return True

        return False

    ############################################################################################################
    def has_prop_archive(self, prop_name: str) -> bool:
        return prop_name in self._prop_archives


############################################################################################################
