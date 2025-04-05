from loguru import logger
from typing import List, Union, Any, Optional, Final
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langserve import RemoteRunnable
from llm_serves.request_protocol import (
    RequestModel,
    ResponseModel,
)


class ChatRequestHandler:

    ################################################################################################################################################################################
    def __init__(
        self,
        name: str,
        prompt: str,
        chat_history: List[Union[SystemMessage, HumanMessage, AIMessage]],
        user_name: str = "",
    ) -> None:

        self._name = name
        self._prompt: Final[str] = prompt
        self._chat_history: List[Union[SystemMessage, HumanMessage, AIMessage]] = (
            chat_history
        )
        self._response: Optional[ResponseModel] = None
        self._user_name: str = user_name

    ################################################################################################################################################################################
    @property
    def response_content(self) -> str:
        if self._response is None:
            return ""
        return self._response.output

    ################################################################################################################################################################################
    def request(self, remote_runnable: RemoteRunnable[Any, Any]) -> Optional[Any]:

        assert self._response is None

        if self._prompt == "":
            logger.error(f"{self._name}: request error: prompt is empty")
            return None

        try:

            logger.debug(f"{self._name} request prompt:\n{self._prompt}")

            response = remote_runnable.invoke(
                RequestModel(
                    agent_name=self._name,
                    user_name=self._user_name,
                    input=self._prompt,
                    chat_history=self._chat_history,
                )
            )

            self._response = ResponseModel.model_validate(response)
            logger.info(
                f"{self._name} request-response:\n{self._response.model_dump_json()}"
            )

        except Exception as e:
            logger.error(f"{self._name}: request error: {e}")

        return self._response

    ################################################################################################################################################################################
    async def a_request(
        self, remote_runnable: RemoteRunnable[Any, Any]
    ) -> Optional[Any]:
        assert self._response is None

        if self._prompt == "":
            logger.error(f"{self._name}: a_request error: prompt is empty")
            return None

        try:

            logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")

            response = await remote_runnable.ainvoke(
                RequestModel(
                    agent_name=self._name,
                    user_name=self._user_name,
                    input=self._prompt,
                    chat_history=self._chat_history,
                )
            )

            self._response = ResponseModel.model_validate(response)
            logger.info(
                f"{self._name} a_request-response:\n{self._response.model_dump_json()}"
            )

        except Exception as e:
            logger.error(f"{self._name}: a_request error: {e}")

        return self._response

    ################################################################################################################################################################################
