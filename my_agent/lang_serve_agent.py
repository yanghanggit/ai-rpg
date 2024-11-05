from langserve import RemoteRunnable  # type: ignore
from typing import List, Union, Optional, final
from langchain_core.messages import HumanMessage, AIMessage
from my_agent.remote_runnable_wrapper import RemoteRunnableWrapper


@final
class LangServeAgent:

    def __init__(
        self, name: str, remote_runnable_wrapper: RemoteRunnableWrapper
    ) -> None:
        self._name: str = name
        self._remote_runnable_wrapper: RemoteRunnableWrapper = remote_runnable_wrapper
        self._chat_history: List[Union[HumanMessage, AIMessage]] = []

    @property
    def remote_runnable(self) -> Optional[RemoteRunnable]:
        return self._remote_runnable_wrapper._remote_runnable
