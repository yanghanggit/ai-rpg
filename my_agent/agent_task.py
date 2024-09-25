from loguru import logger
from typing import Dict, List, Union, cast, Any
from langchain_core.messages import HumanMessage, AIMessage
import asyncio
import time
from my_agent.lang_serve_agent import LangServeAgent
from enum import Flag, auto


class OptionsForContextOperation(Flag):
    NONE = auto()
    INPUT_CHAT_HISTORY = auto()
    APPEND_PROMPT_TO_CHAT_HISTORY = auto()
    APPEND_RESPONSE_TO_CHAT_HISTORY = auto()


class AgentTask:

    ################################################################################################################################################################################
    @staticmethod
    async def gather(tasks: List["AgentTask"]) -> List[Any]:
        coros = [task.a_request() for task in tasks]
        start_time = time.time()
        future = await asyncio.gather(*coros)
        end_time = time.time()

        logger.debug(f"AgentTask.gather:{end_time - start_time:.2f} seconds")
        return future

    ################################################################################################################################################################################
    @staticmethod
    def create(
        agent: LangServeAgent,
        prompt: str,
    ) -> "AgentTask":
        return AgentTask(
            agent,
            prompt,
            OptionsForContextOperation.INPUT_CHAT_HISTORY
            | OptionsForContextOperation.APPEND_PROMPT_TO_CHAT_HISTORY
            | OptionsForContextOperation.APPEND_RESPONSE_TO_CHAT_HISTORY,
        )

    ################################################################################################################################################################################
    @staticmethod
    def create_standalone(agent: LangServeAgent, prompt: str) -> "AgentTask":
        return AgentTask(agent, prompt, OptionsForContextOperation.NONE)

    ################################################################################################################################################################################
    @staticmethod
    def create_process_context_without_saving(
        agent: LangServeAgent, prompt: str
    ) -> "AgentTask":
        return AgentTask(agent, prompt, OptionsForContextOperation.INPUT_CHAT_HISTORY)

    ################################################################################################################################################################################
    def __init__(
        self,
        agent: LangServeAgent,
        prompt: str,
        options_for_context_opt: OptionsForContextOperation,
    ) -> None:

        assert prompt != ""

        self._agent: LangServeAgent = agent
        self._prompt: str = prompt
        self._response: Any = None
        self._extend_params: Dict[str, str] = {}
        self._options_for_context_opt: OptionsForContextOperation = (
            options_for_context_opt
        )

    ################################################################################################################################################################################
    @property
    def agent_name(self) -> str:
        return self._agent._name

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

        if (
            OptionsForContextOperation.INPUT_CHAT_HISTORY
            in self._options_for_context_opt
        ):
            return self._agent._chat_history
        return []

    ################################################################################################################################################################################
    def request(self) -> Any:

        assert self.response is None

        if self._agent.remote_runnable is None:
            return None

        try:

            logger.info(f"{self.agent_name} request prompt:\n{self._prompt}")

            self._response = self._agent.remote_runnable.invoke(
                {
                    "input": self._prompt,
                    "chat_history": self.chat_history_as_context,
                }
            )

            if self.response is not None:
                self._finalize_task()
                logger.info(
                    f"{self.agent_name} request success:\n{self.response_content}"
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

            logger.info(f"{self.agent_name} a_request prompt:\n{self._prompt}")

            self._response = await self._agent.remote_runnable.ainvoke(
                {
                    "input": self._prompt,
                    "chat_history": self.chat_history_as_context,
                }
            )

            if self.response is not None:
                self._finalize_task()
                logger.info(
                    f"{self.agent_name} a_request success:\n{self.response_content}"
                )

        except Exception as e:
            logger.error(f"{self.agent_name}: a_request error: {e}")

        return self.response

    ################################################################################################################################################################################
    def _finalize_task(self) -> None:

        if (
            OptionsForContextOperation.APPEND_PROMPT_TO_CHAT_HISTORY
            in self._options_for_context_opt
        ):
            self._agent._chat_history.extend([HumanMessage(content=self._prompt)])

        if (
            OptionsForContextOperation.APPEND_RESPONSE_TO_CHAT_HISTORY
            in self._options_for_context_opt
        ):
            self._agent._chat_history.extend([AIMessage(content=self.response_content)])

    ################################################################################################################################################################################
