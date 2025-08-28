from typing import Final, Optional, cast, final

import httpx
import requests
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger

from .protocol import (
    ChatRequest,
    ChatRequestMessageListType,
    ChatResponse,
)


@final
class ChatClient:

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

        self._chat_response: ChatResponse = ChatResponse()
        self._timeout: Final[int] = timeout if timeout is not None else 30

        for message in self._chat_history:
            assert isinstance(message, (HumanMessage, AIMessage, SystemMessage))

    ################################################################################################################################################################################
    @property
    def last_message_content(self) -> str:
        if len(self._chat_response.messages) == 0:
            return ""
        return cast(str, self._chat_response.messages[-1].content)

    ################################################################################################################################################################################
    @property
    def ai_message(self) -> AIMessage:
        for message in reversed(self._chat_response.messages):
            if isinstance(message, AIMessage):
                return message

        return AIMessage(content="")

    ################################################################################################################################################################################
    def request(self, url: str) -> None:

        try:

            logger.debug(f"{self._name} request prompt:\n{self._prompt}")

            response = requests.post(
                url=url,
                json=ChatRequest(
                    message=HumanMessage(content=self._prompt),
                    chat_history=self._chat_history,
                ).model_dump(),
                timeout=self._timeout,
            )

            if response.status_code == 200:
                self._chat_response = ChatResponse.model_validate(response.json())
                logger.info(
                    f"{self._name} request-response:\n{self._chat_response.model_dump_json()}"
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
                json=ChatRequest(
                    message=HumanMessage(content=self._prompt),
                    chat_history=self._chat_history,
                ).model_dump(),
                timeout=self._timeout,
            )

            if response.status_code == 200:
                self._chat_response = ChatResponse.model_validate(response.json())
                logger.info(
                    f"{self._name} a_request-response:\n{self._chat_response.model_dump_json()}"
                )
            else:
                logger.error(
                    f"a_request-response Error: {response.status_code}, {response.text}"
                )

        except Exception as e:
            logger.error(f"{self._name}: a_request error: {e}")

    ################################################################################################################################################################################
