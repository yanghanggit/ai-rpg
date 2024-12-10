from loguru import logger
from typing import List, Union, cast, Any, Optional, override
from langchain_core.messages import HumanMessage, AIMessage
from agent.task_request_handler import TaskRequestHandler
from agent.lang_serve_agent import LangServeAgent
from enum import Flag, auto


################################################################################################################################################################################
class ChatHistoryOperationOptions(Flag):
    NONE = auto()
    INPUT_CHAT_HISTORY = auto()
    APPEND_PROMPT_TO_CHAT_HISTORY = auto()
    APPEND_RESPONSE_TO_CHAT_HISTORY = auto()


################################################################################################################################################################################


class AgentRequestHandler(TaskRequestHandler):

    ################################################################################################################################################################################
    @staticmethod
    def create_with_full_context(
        agent: LangServeAgent,
        prompt: str,
    ) -> "AgentRequestHandler":
        return AgentRequestHandler(
            agent,
            prompt,
            ChatHistoryOperationOptions.INPUT_CHAT_HISTORY
            | ChatHistoryOperationOptions.APPEND_PROMPT_TO_CHAT_HISTORY
            | ChatHistoryOperationOptions.APPEND_RESPONSE_TO_CHAT_HISTORY,
        )

    ################################################################################################################################################################################
    @staticmethod
    def create_without_context(
        agent: LangServeAgent, prompt: str
    ) -> "AgentRequestHandler":
        return AgentRequestHandler(agent, prompt, ChatHistoryOperationOptions.NONE)

    ################################################################################################################################################################################
    @staticmethod
    def create_with_input_only_context(
        agent: LangServeAgent, prompt: str
    ) -> "AgentRequestHandler":
        return AgentRequestHandler(
            agent, prompt, ChatHistoryOperationOptions.INPUT_CHAT_HISTORY
        )

    ################################################################################################################################################################################
    def __init__(
        self,
        agent: LangServeAgent,
        prompt: str,
        context_operation_options: ChatHistoryOperationOptions,
    ) -> None:

        self._agent: LangServeAgent = agent
        self._prompt: str = prompt
        self._response: Optional[Any] = None
        self._chat_history_options: ChatHistoryOperationOptions = (
            context_operation_options
        )

    ################################################################################################################################################################################
    @property
    def agent_name(self) -> str:
        return self._agent.name

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
    @property
    def chat_history_as_context(self) -> List[Union[HumanMessage, AIMessage]]:

        if ChatHistoryOperationOptions.INPUT_CHAT_HISTORY in self._chat_history_options:
            return self._agent._chat_history
        return []

    ################################################################################################################################################################################
    @override
    def request(self) -> Optional[Any]:
        assert self.response is None
        if self._agent.remote_runnable is None:
            return None

        if self._prompt == "":
            logger.error(f"{self.agent_name}: request error: prompt is empty")
            return None

        try:

            logger.debug(f"{self.agent_name} request prompt:\n{self._prompt}")

            self._response = self._agent.remote_runnable.invoke(
                {
                    "input": self._prompt,
                    "chat_history": self.chat_history_as_context,
                }
            )

            if self.response is not None:
                self._update_chat_history()
                logger.info(
                    f"{self.agent_name} request response:\n{self.response_content}"
                )

        except Exception as e:
            logger.error(f"{self.agent_name}: request error: {e}")

        return self.response

    ################################################################################################################################################################################
    @override
    async def a_request(self) -> Optional[Any]:
        assert self.response is None
        if self._agent.remote_runnable is None:
            return None

        if self._prompt == "":
            logger.error(f"{self.agent_name}: a_request error: prompt is empty")
            return None

        try:

            logger.debug(f"{self.agent_name} a_request prompt:\n{self._prompt}")

            self._response = await self._agent.remote_runnable.ainvoke(
                {
                    "input": self._prompt,
                    "chat_history": self.chat_history_as_context,
                }
            )

            if self.response is not None:
                self._update_chat_history()
                logger.info(
                    f"{self.agent_name} a_request response:\n{self.response_content}"
                )

        except Exception as e:
            logger.error(f"{self.agent_name}: a_request error: {e}")

        return self.response

    ################################################################################################################################################################################
    def _update_chat_history(self) -> None:

        if (
            ChatHistoryOperationOptions.APPEND_PROMPT_TO_CHAT_HISTORY
            in self._chat_history_options
        ):
            self._agent._chat_history.extend([HumanMessage(content=self._prompt)])

        if (
            ChatHistoryOperationOptions.APPEND_RESPONSE_TO_CHAT_HISTORY
            in self._chat_history_options
        ):
            self._agent._chat_history.extend([AIMessage(content=self.response_content)])

    ################################################################################################################################################################################
