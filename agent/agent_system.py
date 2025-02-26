from loguru import logger
from typing import Dict, List, Optional, Set, cast, final
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pathlib import Path
from agent.lang_serve_agent import LangServeAgent
from agent.remote_runnable_handler import RemoteRunnableHandler
from rpg_models.agent_models import (
    AgentMessageType,
    AgentMessageModel,
    AgentChatHistoryDumpModel,
)


@final
class AgentSystem:

    def __init__(self) -> None:
        self._agents: Dict[str, LangServeAgent] = {}
        self._runtime_dir: Optional[Path] = None
        self._remote_runnable_handlers: Dict[str, RemoteRunnableHandler] = {}

    ################################################################################################################################################################################
    ### 必须设置根部的执行路行
    def set_runtime_dir(self, runtime_dir: Path) -> None:
        assert runtime_dir is not None
        self._runtime_dir = runtime_dir
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        assert runtime_dir.exists()
        assert (
            self._runtime_dir.is_dir()
        ), f"Directory is not a directory: {self._runtime_dir}"

    ################################################################################################################################################################################
    def register_agent(self, agent_name: str, url: str) -> LangServeAgent:

        assert not agent_name in self._agents
        if agent_name in self._agents:
            logger.error(f"register_agent: {agent_name} has been registered.")
            return self._agents[agent_name]

        remote_runnable = self._remote_runnable_handlers.get(url, None)
        if remote_runnable is None:
            remote_runnable = RemoteRunnableHandler(url)
            self._remote_runnable_handlers[url] = remote_runnable

        new_agent = LangServeAgent(agent_name, remote_runnable)
        self._agents[agent_name] = new_agent
        return new_agent

    ################################################################################################################################################################################
    def get_agent(self, agent_name: str) -> Optional[LangServeAgent]:
        return self._agents.get(agent_name, None)

    ################################################################################################################################################################################
    def append_human_message(self, agent_name: str, chat: str) -> None:
        agent = self.get_agent(agent_name)
        assert agent is not None, f"add_chat_history: {agent_name} is not registered."
        if agent is not None:
            agent._chat_history.extend([HumanMessage(content=chat)])

    ################################################################################################################################################################################
    def append_ai_message(self, agent_name: str, chat: str) -> None:
        agent = self.get_agent(agent_name)
        assert agent is not None, f"add_chat_history: {agent_name} is not registered."
        if agent is not None:
            agent._chat_history.extend([AIMessage(content=chat)])

    ################################################################################################################################################################################
    def append_system_message(self, agent_name: str, chat: str) -> None:
        agent = self.get_agent(agent_name)
        assert agent is not None, f"add_chat_history: {agent_name} is not registered."
        if agent is not None:
            agent._chat_history.extend([SystemMessage(content=f"{chat}")])

    ################################################################################################################################################################################
    def discard_last_human_ai_conversation(
        self, agent_name: str
    ) -> List[SystemMessage | HumanMessage | AIMessage]:

        agent = self.get_agent(agent_name)
        if agent is None:
            return []

        chat_history = agent._chat_history
        if len(chat_history) == 0:
            return []

        if not isinstance(chat_history[-1], AIMessage):
            ## 最后一次不是AI的回答，就跳出，因为可能是有问题的。ai还没有回答，只有人的问题
            return []

        ## 是AI的回答，需要删除AI的回答和人的问题
        ret: List[SystemMessage | HumanMessage | AIMessage] = []

        ai_message = chat_history.pop()
        ret.insert(0, ai_message)

        ## 删除人的问题，直到又碰见AI的回答，就跳出
        for i in range(len(chat_history) - 1, -1, -1):
            if isinstance(chat_history[i], HumanMessage):
                human_message = chat_history.pop(i)
                ret.insert(0, human_message)
            else:
                break

        return ret

    ################################################################################################################################################################################
    def _resolve_chat_history_dump_file_path(self, name: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{name}"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"chat_history.json"

    ################################################################################################################################################################################
    def dump_chat_histories(self) -> Dict[str, int]:

        ret: Dict[str, int] = {}

        for agent_name in self._agents.keys():

            try:

                agent_chat_history_json = self._retrieve_chat_history(
                    agent_name
                ).model_dump_json()

                path = self._resolve_chat_history_dump_file_path(agent_name)
                ret[agent_name] = path.write_text(
                    agent_chat_history_json, encoding="utf-8"
                )

            except Exception as e:
                logger.error(f"[{agent_name}]写入chat history dump失败。{e}")

        return ret

    ################################################################################################################################################################################
    def _retrieve_chat_history(self, agent_name: str) -> AgentChatHistoryDumpModel:
        agent = self.get_agent(agent_name)
        if agent is None:
            return AgentChatHistoryDumpModel(name="", url="", chat_history=[])

        ret: AgentChatHistoryDumpModel = AgentChatHistoryDumpModel(
            name=agent_name, url=agent.remote_connector.url, chat_history=[]
        )

        for message in agent._chat_history:
            if isinstance(message, HumanMessage):
                ret.chat_history.append(
                    AgentMessageModel(
                        message_type=AgentMessageType.HUMAN,
                        content=cast(str, message.content),
                    )
                )
            elif isinstance(message, AIMessage):
                ret.chat_history.append(
                    AgentMessageModel(
                        message_type=AgentMessageType.AI,
                        content=cast(str, message.content),
                    )
                )
            elif isinstance(message, SystemMessage):
                ret.chat_history.append(
                    AgentMessageModel(
                        message_type=AgentMessageType.STSTEM,
                        content=cast(str, message.content),
                    )
                )

        return ret

    ################################################################################################################################################################################
    def replace_messages(self, name: str, message_replacements: Dict[str, str]) -> None:

        agent = self.get_agent(name)
        if agent is None:
            return

        for key_word, replace_content in message_replacements.items():
            extracted_messages = self._extract_human_or_ai_messages_by_keywords(
                name, {key_word}
            )
            for message in extracted_messages:
                message.content = replace_content

    ################################################################################################################################################################################
    def _extract_human_or_ai_messages_by_keywords(
        self, name: str, filtered_words: Set[str]
    ) -> List[HumanMessage | AIMessage]:

        agent = self.get_agent(name)
        if agent is None:
            return []

        ret: List[HumanMessage | AIMessage] = []
        for message in agent._chat_history:
            if isinstance(message, SystemMessage):
                continue
            for content in filtered_words:
                if content in cast(str, message.content):
                    ret.append(message)
        return ret

    ################################################################################################################################################################################
    # def remove_excluded_messages(
    #     self, name: str, excluded_messages: List[HumanMessage | AIMessage]
    # ) -> None:

    #     agent = self.get_agent(name)
    #     if agent is None:
    #         return

    #     shallow_copy = agent._chat_history.copy()
    #     for message in excluded_messages:
    #         if message in shallow_copy:
    #             shallow_copy.remove(message)

    ################################################################################################################################################################################
    def initialize_chat_history(
        self, name: str, chat_history_dump_model: AgentChatHistoryDumpModel
    ) -> None:
        agent = self.get_agent(name)
        if agent is None:
            return

        assert len(agent._chat_history) == 0
        agent._chat_history.clear()
        for message in chat_history_dump_model.chat_history:
            if message.message_type == AgentMessageType.HUMAN:
                agent._chat_history.extend([HumanMessage(content=message.content)])
            elif message.message_type == AgentMessageType.AI:
                agent._chat_history.extend([AIMessage(content=message.content)])
            elif message.message_type == AgentMessageType.STSTEM:
                agent._chat_history.extend([SystemMessage(content=message.content)])

    ################################################################################################################################################################################
