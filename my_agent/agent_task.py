from loguru import logger
from typing import Dict, List, Union, cast, Any
from langchain_core.messages import HumanMessage, AIMessage
import asyncio
import time
from my_agent.lang_serve_agent import LangServeAgent


class AgentTask:

    ################################################################################################################################################################################
    @staticmethod
    def create(agent: LangServeAgent, prompt: str) -> "AgentTask":
        return AgentTask(agent, prompt)

    ################################################################################################################################################################################
    @staticmethod
    def create_standalone(agent: LangServeAgent, prompt: str) -> "AgentTask":

        ret = AgentTask.create(agent, prompt)

        ret._option_input_chat_history = False
        ret._option_add_prompt_to_chat_history = False
        ret._option_add_response_to_chat_history = False

        return ret

    ################################################################################################################################################################################
    @staticmethod
    def create_process_context_without_saving(
        agent: LangServeAgent, prompt: str
    ) -> "AgentTask":

        ret = AgentTask.create(agent, prompt)

        ret._option_input_chat_history = True
        ret._option_add_prompt_to_chat_history = False
        ret._option_add_response_to_chat_history = False

        return ret

    ################################################################################################################################################################################
    def __init__(self, agent: LangServeAgent, prompt: str) -> None:

        assert prompt != ""

        self._agent: LangServeAgent = agent
        self._prompt: str = prompt
        self._option_input_chat_history: bool = True
        self._option_add_prompt_to_chat_history: bool = True
        self._option_add_response_to_chat_history: bool = True
        self._response: Any = None
        self._extend_params: Dict[str, str] = {}

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
        return self._option_input_chat_history and self._agent._chat_history or []

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

        if self._option_add_prompt_to_chat_history:
            self._agent._chat_history.extend([HumanMessage(content=self._prompt)])

        if self._option_add_response_to_chat_history:
            self._agent._chat_history.extend([AIMessage(content=self.response_content)])

    ################################################################################################################################################################################


################################################################################################################################################################################
################################################################################################################################################################################
################################################################################################################################################################################
class AgentTasksGather:

    def __init__(self, name: str, tasks: List[AgentTask]) -> None:
        self._name: str = name
        self._tasks: List[AgentTask] = tasks

    # 核心方法
    async def _gather(self) -> List[Any]:
        tasks = [task.a_request() for task in self._tasks]
        future = await asyncio.gather(*tasks)
        return future

    # 当确定全部异步请求任务添加完毕后，调用这个方法，等待所有任务完成，并拿到任务结果
    async def gather(self) -> List[Any]:
        start_time = time.time()
        ret = await self._gather()  # 调用async_gather，等待所有任务完成，并拿到任务结果
        end_time = time.time()
        logger.debug(
            f"{self._name} run_async_requet_tasks time: {end_time - start_time:.2f} seconds"
        )
        return ret
