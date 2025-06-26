from loguru import logger
from typing import Optional, Final, final
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import httpx
from chat_services.chat_api import (
    ChatRequestModel,
    ChatResponseModel,
    ChatRequestMessageListType,
)
import requests


@final
class ChatRequestHandler:

    ################################################################################################################################################################################
    def __init__(
        self,
        agent_name: str,
        prompt: str,
        chat_history: ChatRequestMessageListType,
        timeout: Optional[int] = None,
    ) -> None:

        self._name = agent_name
        assert self._name != "", "agent_name should not be empty"

        self._prompt: Final[str] = prompt
        assert self._prompt != "", "prompt should not be empty"

        self._chat_history: ChatRequestMessageListType = chat_history
        if len(self._chat_history) == 0:
            logger.warning(f"{self._name}: chat_history is empty")

        self._response: Optional[ChatResponseModel] = None
        self._timeout: Final[int] = timeout if timeout is not None else 30

        for message in self._chat_history:
            assert isinstance(message, (HumanMessage, AIMessage, SystemMessage))

    ################################################################################################################################################################################
    @property
    def last_response_message_content(self) -> str:
        if self._response is None:
            return ""
        return self._response.output

    ################################################################################################################################################################################
    def request(self, url: str) -> None:

        try:

            logger.debug(f"{self._name} request prompt:\n{self._prompt}")

            response = requests.post(
                url=url,
                json=ChatRequestModel(
                    input=self._prompt,
                    chat_history=self._chat_history,
                ).model_dump(),
                timeout=self._timeout,
            )

            if response.status_code == 200:
                self._response = ChatResponseModel.model_validate(response.json())
                logger.info(
                    f"{self._name} request-response:\n{self._response.model_dump_json()}"
                )
            else:
                logger.error(
                    f"request-response Error: {response.status_code}, {response.text}"
                )

        except Exception as e:
            logger.error(f"{self._name}: request error: {e}")

    ################################################################################################################################################################################
    async def a_request(self, client: httpx.AsyncClient, url: str) -> None:

        try:

            logger.debug(f"{self._name} a_request prompt:\n{self._prompt}")

            response = await client.post(
                url=url,
                json=ChatRequestModel(
                    input=self._prompt,
                    chat_history=self._chat_history,
                ).model_dump(),
                timeout=self._timeout,
            )

            if response.status_code == 200:
                self._response = ChatResponseModel.model_validate(response.json())
                logger.info(
                    f"{self._name} a_request-response:\n{self._response.model_dump_json()}"
                )
            else:
                logger.error(
                    f"a_request-response Error: {response.status_code}, {response.text}"
                )

        except Exception as e:
            logger.error(f"{self._name}: a_request error: {e}")

    ################################################################################################################################################################################
