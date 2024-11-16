from langserve import RemoteRunnable  # type: ignore
from typing import List, Union, Optional, final
from langchain_core.messages import HumanMessage, AIMessage
from my_agent.remote_runnable_connector import RemoteRunnableConnector


@final
class LangServeAgent:

    @staticmethod
    def create_empty() -> "LangServeAgent":
        return LangServeAgent("", RemoteRunnableConnector(""))

    def __init__(self, name: str, remote_connector: RemoteRunnableConnector) -> None:
        self._name: str = name
        self._remote_connector: RemoteRunnableConnector = remote_connector
        self._chat_history: List[Union[HumanMessage, AIMessage]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def remote_connector(self) -> RemoteRunnableConnector:
        return self._remote_connector

    @property
    def remote_runnable(self) -> Optional[RemoteRunnable]:
        return self._remote_connector._remote_runnable
