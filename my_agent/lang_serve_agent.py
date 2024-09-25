from langserve import RemoteRunnable  # type: ignore
from loguru import logger
from typing import List, Union, Optional
from langchain_core.messages import HumanMessage, AIMessage
from my_agent.remote_runnable_wrapper import RemoteRunnableWrapper


class LangServeAgent:

    def __init__(
        self, name: str, remote_runnable_wrapper: RemoteRunnableWrapper
    ) -> None:
        self._name: str = name
        self._remote_runnable_wrapper: RemoteRunnableWrapper = remote_runnable_wrapper
        self._chat_history: List[Union[HumanMessage, AIMessage]] = []

    def initialize_connection(self) -> None:
        self._remote_runnable_wrapper._initialize_connection()

    @property
    def remote_runnable(self) -> Optional[RemoteRunnable]:
        return self._remote_runnable_wrapper._remote_runnable
