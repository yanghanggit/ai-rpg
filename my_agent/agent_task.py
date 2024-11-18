from loguru import logger
from typing import List, Union, cast, Any
from langchain_core.messages import HumanMessage, AIMessage
import asyncio

# import time
from my_agent.lang_serve_agent import LangServeAgent
from enum import Flag, auto


class ChatHistoryOperationOptions(Flag):
    NONE = auto()
    INPUT_CHAT_HISTORY = auto()
    APPEND_PROMPT_TO_CHAT_HISTORY = auto()
    APPEND_RESPONSE_TO_CHAT_HISTORY = auto()


class AgentTask:

    ################################################################################################################################################################################
    @staticmethod
    async def gather(tasks: List["AgentTask"]) -> List[Any]:
        coros = [task.a_request() for task in tasks]
        # start_time = time.time()
        future = await asyncio.gather(*coros)
        # end_time = time.time()
        # logger.debug(f"AgentTask.gather:{end_time - start_time:.2f} seconds")
        return future

    ################################################################################################################################################################################
    @staticmethod
    def create_with_full_context(
        agent: LangServeAgent,
        prompt: str,
    ) -> "AgentTask":
        return AgentTask(
            agent,
            prompt,
            ChatHistoryOperationOptions.INPUT_CHAT_HISTORY
            | ChatHistoryOperationOptions.APPEND_PROMPT_TO_CHAT_HISTORY
            | ChatHistoryOperationOptions.APPEND_RESPONSE_TO_CHAT_HISTORY,
        )

    ################################################################################################################################################################################
    @staticmethod
    def create_without_context(agent: LangServeAgent, prompt: str) -> "AgentTask":
        return AgentTask(agent, prompt, ChatHistoryOperationOptions.NONE)

    ################################################################################################################################################################################
    @staticmethod
    def create_with_input_only_context(
        agent: LangServeAgent, prompt: str
    ) -> "AgentTask":
        return AgentTask(agent, prompt, ChatHistoryOperationOptions.INPUT_CHAT_HISTORY)

    ################################################################################################################################################################################
    def __init__(
        self,
        agent: LangServeAgent,
        prompt: str,
        context_operation_options: ChatHistoryOperationOptions,
    ) -> None:

        assert prompt != ""

        self._agent: LangServeAgent = agent
        self._prompt: str = prompt
        self._response: Any = None
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
    def response(self) -> Any:
        return self._response

    ################################################################################################################################################################################
    @property
    def chat_history_as_context(self) -> List[Union[HumanMessage, AIMessage]]:

        if ChatHistoryOperationOptions.INPUT_CHAT_HISTORY in self._chat_history_options:
            return self._agent._chat_history
        return []

    ################################################################################################################################################################################
    def request(self) -> Any:
        assert self.response is None
        if self._agent.remote_runnable is None:
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
                self._finalize_task()
                logger.info(
                    f"{self.agent_name} request response:\n{self.response_content}"
                )

        except Exception as e:
            logger.error(f"{self.agent_name}: request error: {e}")

        return self.response

    ################################################################################################################################################################################
    async def a_request(self) -> Any:
        assert self.response is None
        if self._agent.remote_runnable is None:
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
                self._finalize_task()
                logger.info(
                    f"{self.agent_name} a_request response:\n{self.response_content}"
                )

        except Exception as e:
            logger.error(f"{self.agent_name}: a_request error: {e}")

        return self.response

    ################################################################################################################################################################################
    def _finalize_task(self) -> None:

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
