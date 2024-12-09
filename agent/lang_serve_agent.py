from langserve import RemoteRunnable  # type: ignore
from typing import Final, List, Union, Optional, final
from langchain_core.messages import HumanMessage, AIMessage
from agent.remote_runnable_handler import RemoteRunnableHandler


@final
class LangServeAgent:

    @staticmethod
    def create_empty() -> "LangServeAgent":
        return LangServeAgent("", RemoteRunnableHandler(""))

    def __init__(self, name: str, remote_connector: RemoteRunnableHandler) -> None:
        self._name: Final[str] = name
        self._remote_connector: Final[RemoteRunnableHandler] = remote_connector
        self._chat_history: List[Union[HumanMessage, AIMessage]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def remote_connector(self) -> RemoteRunnableHandler:
        return self._remote_connector

    @property
    def remote_runnable(self) -> Optional[RemoteRunnable]:
        return self._remote_connector._remote_runnable
