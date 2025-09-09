from typing import Final, List, Optional, final
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
        assert self._timeout > 0, "timeout should be positive"

        for message in self._chat_history:
            assert isinstance(message, (HumanMessage, AIMessage, SystemMessage))

        self._cache_ai_messages: Optional[List[AIMessage]] = None

    ################################################################################################################################################################################
    @property
    def response_content(self) -> str:
        if len(self.ai_messages) == 0:
            return ""

        last_message = self.ai_messages[-1]

        # 处理 content 的不同类型
        content = last_message.content

        # 如果 content 已经是字符串，直接返回
        if isinstance(content, str):
            return content

        # 如果 content 是列表，需要处理列表中的元素
        if isinstance(content, list):
            # 将列表中的每个元素转换为字符串并连接
            content_parts = []
            for item in content:
                if isinstance(item, str):
                    content_parts.append(item)
                elif isinstance(item, dict):
                    # 对于字典类型，转换为 JSON 字符串或简单的字符串表示
                    content_parts.append(str(item))
                else:
                    # 其他类型，直接转换为字符串
                    content_parts.append(str(item))
            return "\n".join(content_parts)

        # 兜底情况：直接转换为字符串
        return str(content)

    ################################################################################################################################################################################
    @property
    def ai_messages(self) -> List[AIMessage]:

        if self._cache_ai_messages is not None:
            return self._cache_ai_messages

        self._cache_ai_messages = []
        for message in self._chat_response.messages:
            if message.type == "ai":
                if isinstance(message, AIMessage):
                    self._cache_ai_messages.append(message)
                else:
                    self._cache_ai_messages.append(
                        AIMessage.model_validate(message.model_dump())
                    )

        # 再检查一次！！！
        for check_message in self._cache_ai_messages:
            assert isinstance(check_message, AIMessage)

        return self._cache_ai_messages

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
