from loguru import logger
from typing import Dict,  List, Union, Optional, cast, Any
from langchain_core.messages import HumanMessage, AIMessage
import asyncio
import time
from my_agent.lang_serve_agent import LangServeAgent

class LangServeAgentRequestTask:

    def __init__(self, 
                 agent: LangServeAgent, 
                 prompt: str,
                 input_chat_history: bool = True,
                 add_prompt_to_chat_history: bool = True, 
                 add_response_to_chat_history: bool = True) -> None:
        
        self._agent: LangServeAgent = agent
        self._prompt: str = prompt
        assert self._prompt is not None and self._prompt != ""
        self._input_chat_history: bool = input_chat_history
        self._add_prompt_to_chat_history: bool = add_prompt_to_chat_history
        self._add_response_to_chat_history: bool = add_response_to_chat_history
        self._response: Any = None
################################################################################################################################################################################
    @property
    def agent_name(self) -> str:
        return self._agent._name
################################################################################################################################################################################
    @property
    def response_content(self) -> str:
        if self._response is None:
            return ""
        return cast(str, self._response['output']) 
################################################################################################################################################################################
    def request(self) -> Optional[str]:

        assert self._response is None

        if self._agent is None or self._agent._remote_runnable is None or self._prompt == "":
            logger.error(f"request: no agent")
            return None
    
        try:

            self._response = self._agent._remote_runnable.invoke({"input": self._prompt, "chat_history": self.input_chat_history_as_context()})
            # 只要能执行到这里，说明LLM运行成功，可能包括政策问题也通过了。
            if self._response is None:
                return None
            
            self.on_request_done()
            logger.debug(f"\n{'=' * 50}\n{self.agent_name} request result:\n{self.response_content}\n{'=' * 50}")
            return self.response_content
           
        except Exception as e:
            logger.error(f"{self.agent_name}: request error: {e}")

        return None
################################################################################################################################################################################
    def input_chat_history_as_context(self) -> List[Union[HumanMessage, AIMessage]]:
        return self._input_chat_history and self._agent._chat_history or []
################################################################################################################################################################################
    def on_request_done(self) -> None:
        assert self._response is not None
        if self._add_prompt_to_chat_history:
            self._agent._chat_history.extend([HumanMessage(content = self._prompt)])

        if self._add_response_to_chat_history:
            assert self.response_content is not None
            self._agent._chat_history.extend([AIMessage(content = self.response_content)])
################################################################################################################################################################################
    async def async_request(self) -> Optional[str]:

        assert self._response is None

        if self._agent is None or self._agent._remote_runnable is None or self._prompt == "":
            logger.error(f"async_request: no agent")
            return None
    
        try:

            self._response = await self._agent._remote_runnable.ainvoke({"input": self._prompt, "chat_history": self.input_chat_history_as_context()})
            # 只要能执行到这里，说明LLM运行成功，可能包括政策问题也通过了。
            if self._response is None:
                return None

            self.on_request_done()
            logger.debug(f"\n{self.agent_name} async_request result:\n{self.response_content}\n")
            return self.response_content
           
        except Exception as e:
            logger.error(f"{self.agent_name}: async_request error: {e}")

        return None
################################################################################################################################################################################
################################################################################################################################################################################
################################################################################################################################################################################
class LangServeAgentAsyncRequestTasksGather:

    def __init__(self, name: str, request_tasks: Dict[str, LangServeAgentRequestTask]) -> None:
        self._name: str = name
        self._async_tasks: Dict[str, LangServeAgentRequestTask] = request_tasks

    # 核心方法
    async def impl_gather(self) -> List[Optional[str]]:
        tasks = [task.async_request() for task in self._async_tasks.values()]
        future = await asyncio.gather(*tasks)
        return future
    
    # 当确定全部异步请求任务添加完毕后，调用这个方法，等待所有任务完成，并拿到任务结果
    async def gather(self) -> List[Optional[str]]:
        start_time = time.time()
        result = await self.impl_gather() # 调用async_gather，等待所有任务完成，并拿到任务结果
        end_time = time.time()
        #logger.debug(f"{self._name} run_async_requet_tasks time: {end_time - start_time:.2f} seconds")
        return result
################################################################################################################################################################################
################################################################################################################################################################################
################################################################################################################################################################################