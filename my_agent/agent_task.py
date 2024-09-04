from loguru import logger
from typing import Dict, List, Union, Optional, cast, Any
from langchain_core.messages import HumanMessage, AIMessage
import asyncio
import time
from my_agent.agent import LangServeAgent


class AgentTask:

    ################################################################################################################################################################################
    @staticmethod
    def create(agent: LangServeAgent, prompt: str) -> Optional["AgentTask"]:
        if agent is None or prompt == "":
            return None
        return AgentTask(agent, prompt)

    ################################################################################################################################################################################
    @staticmethod
    def create_standalone(agent: LangServeAgent, prompt: str) -> Optional["AgentTask"]:
        ret = AgentTask.create(agent, prompt)
        if ret is None:
            return None

        ret._input_chat_history = False
        ret._add_prompt_to_chat_history = False
        ret._add_response_to_chat_history = False
        return ret

    ################################################################################################################################################################################
    @staticmethod
    def create_process_context_without_saving(
        agent: LangServeAgent, prompt: str
    ) -> Optional["AgentTask"]:
        request_task = AgentTask.create(agent, prompt)
        if request_task is None:
            return None

        request_task._input_chat_history = True
        request_task._add_prompt_to_chat_history = False
        request_task._add_response_to_chat_history = False
        return request_task

    ################################################################################################################################################################################
    def __init__(self, agent: LangServeAgent, prompt: str) -> None:

        assert agent is not None
        self._agent: LangServeAgent = agent
        self._prompt: str = prompt
        assert self._prompt != ""
        self._input_chat_history: bool = True
        self._add_prompt_to_chat_history: bool = True
        self._add_response_to_chat_history: bool = True
        self._response: Any = None
        self._option_param: Dict[str, Any] = {}

    ################################################################################################################################################################################
    @property
    def agent_name(self) -> str:
        if self._agent is None:
            return ""
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
    def request(self) -> Optional[str]:

        assert self._response is None

        if (
            self._agent is None
            or self._agent._remote_runnable_wrapper is None
            or self._agent._remote_runnable_wrapper._remote_runnable is None
            or self._prompt == ""
        ):
            logger.error(f"request: no agent")
            return None

        try:

            logger.info(f"{self.agent_name} request prompt:\n{self._prompt}")
            self._response = (
                self._agent._remote_runnable_wrapper._remote_runnable.invoke(
                    {
                        "input": self._prompt,
                        "chat_history": self.input_chat_history_as_context(),
                    }
                )
            )
            # 只要能执行到这里，说明LLM运行成功，可能包括政策问题也通过了。
            if self._response is None:
                return None

            self.on_request_done()
            logger.info(f"{self.agent_name} request success:\n{self.response_content}")
            return self.response_content

        except Exception as e:
            logger.error(f"{self.agent_name}: request error: {e}")

        return None

    ################################################################################################################################################################################
    def input_chat_history_as_context(self) -> List[Union[HumanMessage, AIMessage]]:
        assert self._agent is not None
        return self._input_chat_history and self._agent._chat_history or []

    ################################################################################################################################################################################
    def on_request_done(self) -> None:
        assert self._agent is not None
        assert self._response is not None
        if self._add_prompt_to_chat_history:
            self._agent._chat_history.extend([HumanMessage(content=self._prompt)])

        if self._add_response_to_chat_history:
            assert self.response_content is not None
            self._agent._chat_history.extend([AIMessage(content=self.response_content)])

    ################################################################################################################################################################################
    async def a_request(self) -> Optional[str]:

        assert self._response is None

        if (
            self._agent is None
            or self._agent._remote_runnable_wrapper is None
            or self._agent._remote_runnable_wrapper._remote_runnable is None
            or self._prompt == ""
        ):
            logger.error(f"a_request: no agent")
            return None

        try:

            logger.info(f"{self.agent_name} a_request prompt:\n{self._prompt}")
            self._response = (
                await self._agent._remote_runnable_wrapper._remote_runnable.ainvoke(
                    {
                        "input": self._prompt,
                        "chat_history": self.input_chat_history_as_context(),
                    }
                )
            )
            # 只要能执行到这里，说明LLM运行成功，可能包括政策问题也通过了。
            if self._response is None:
                return None

            self.on_request_done()
            logger.info(
                f"{self.agent_name} a_request success:\n{self.response_content}"
            )
            return self.response_content

        except Exception as e:
            logger.error(f"{self.agent_name}: a_request error: {e}")

        return None


################################################################################################################################################################################
################################################################################################################################################################################
################################################################################################################################################################################
class AgentTasksGather:

    def __init__(self, name: str, tasks: List[AgentTask]) -> None:
        self._name: str = name
        self._tasks: List[AgentTask] = tasks

    # 核心方法
    async def _gather(self) -> List[Optional[str]]:
        # tasks = [task.a_request() for task in self._tasks.values()]
        tasks = [task.a_request() for task in self._tasks if task is not None]
        future = await asyncio.gather(*tasks)
        return future

    # 当确定全部异步请求任务添加完毕后，调用这个方法，等待所有任务完成，并拿到任务结果
    async def gather(self) -> List[Optional[str]]:
        start_time = time.time()
        result = (
            await self._gather()
        )  # 调用async_gather，等待所有任务完成，并拿到任务结果
        end_time = time.time()
        logger.debug(
            f"{self._name} run_async_requet_tasks time: {end_time - start_time:.2f} seconds"
        )
        return result
