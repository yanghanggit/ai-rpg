from loguru import logger
from typing import List, Union, cast, Any, Optional, Final
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langserve import RemoteRunnable
from typing import List, Any
from loguru import logger


class ChatRequestHandler:

    ################################################################################################################################################################################
    def __init__(
        self,
        name: str,
        prompt: str,
        chat_history: List[Union[SystemMessage, HumanMessage, AIMessage]],
    ) -> None:

        self._name = name
        self._prompt: Final[str] = prompt
        self._chat_history: List[Union[SystemMessage, HumanMessage, AIMessage]] = (
            chat_history
        )
        self._response: Optional[Any] = None
        self._additional_params: List[Any] = []

    ################################################################################################################################################################################
    @property
    def response_content(self) -> str:
        if self._response is None:
            return ""
        return cast(str, self._response["output"])

    ################################################################################################################################################################################
    @property
    def response(self) -> Optional[Any]:
        return self._response

    ################################################################################################################################################################################
    def request(self, remote_runnable: RemoteRunnable[Any, Any]) -> Optional[Any]:
        assert self.response is None

        if self._prompt == "":
            logger.error(f"{self._name}: request error: prompt is empty")
            return None

        try:

            logger.debug(f"{self._name} request prompt:\n{self._prompt}")

            self._response = remote_runnable.invoke(
                {
                    "agent_name": self._name,
                    "user_name": "",
                    "input": self._prompt,
                    "chat_history": self._chat_history,
                }
            )

            logger.info(
                f"{self._name} request response_content:\n{self.response_content}"
            )

        except Exception as e:
            logger.error(f"{self._name}: request error: {e}")

        return self.response

    ################################################################################################################################################################################
    async def a_request(
        self, remote_runnable: RemoteRunnable[Any, Any]
    ) -> Optional[Any]:
        assert self.response is None

        if self._prompt == "":
            logger.error(f"{self._name}: a_request error: prompt is empty")
            return None

        try:

            logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")

            self._response = await remote_runnable.ainvoke(
                {
                    "agent_name": self._name,
                    "user_name": "",
                    "input": self._prompt,
                    "chat_history": self._chat_history,
                }
            )

            logger.info(
                f"{self._name} a_request response_content:\n{self.response_content}"
            )

        except Exception as e:
            logger.error(f"{self._name}: a_request error: {e}")

        return self.response

    ################################################################################################################################################################################
