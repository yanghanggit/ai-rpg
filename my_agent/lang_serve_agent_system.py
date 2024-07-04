from loguru import logger
from typing import Dict,  List, Union, Optional, Set, cast
from langchain_core.messages import HumanMessage, AIMessage
import json
import asyncio
import time
from langserve import RemoteRunnable  # type: ignore
from enum import Enum
from pathlib import Path

# 在 request成功后，决定如何处理 prompt 与 response
class AddChatHistoryOptionOnRequestSuccess(Enum):
    ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY = 1000, # 常规都加
    ADD_PROMPT_TO_CHAT_HISTORY = 2000 # 这是一种特殊情况的处理，只加入prompt，不加入response。这个目前用于对话。因为对话内容在prompt里，如果LLM能response就说明LLM的政策过了。
    NOT_ADD_ANY_TO_CHAT_HISTORY = 3000 # 使用这个要十分小心
  
#
class LangServeAgent:

    def __init__(self, name: str, url: str) -> None:
 
        self._name: str = name 
        self._url: str = url
        self._remote_runnable: RemoteRunnable = None
        self._chat_history: List[Union[HumanMessage, AIMessage]] = []
################################################################################################################################################################################
    def connect(self) -> bool:
        if self._url == "":
            logger.error(f"connect: {self._name} have no url. 请确认是默认玩家，否则检查game_settings.json中配置。")
            return False
        try:
            self._remote_runnable = RemoteRunnable(self._url)
            assert self._remote_runnable is not None
            self._chat_history = []
            return True
        except Exception as e:
            logger.error(e)
            return False        
        return False
################################################################################################################################################################################
    def __str__(self) -> str:
        return f"ActorAgent({self._name}, {self._url})"
################################################################################################################################################################################
    def _handle_chat_history_on_request_success(self, prompt: str, reponse_content: str, option: AddChatHistoryOptionOnRequestSuccess) -> None:
        match(option):

            case AddChatHistoryOptionOnRequestSuccess.ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY:
                self._chat_history.extend([HumanMessage(content = prompt), AIMessage(content = reponse_content)])

            case AddChatHistoryOptionOnRequestSuccess.ADD_PROMPT_TO_CHAT_HISTORY:
                logger.debug(f"add_chat_history: {self._name} add prompt to chat history. 这是一种特殊情况的处理")
                self._chat_history.extend([HumanMessage(content = prompt)])

            case AddChatHistoryOptionOnRequestSuccess.NOT_ADD_ANY_TO_CHAT_HISTORY:
                logger.debug(f"add_chat_history: {self._name} do not add message to chat history.")

            case _:
                logger.error(f"add_chat_history: {self._name} option is not defined.")
################################################################################################################################################################################
    def request(self, prompt: str, option: AddChatHistoryOptionOnRequestSuccess) -> Optional[str]:

        if self._remote_runnable is None:
            logger.error(f"request: {self._name} have no agent.请确认是默认玩家，否则检查game_settings.json中配置。")
            return None
    
        try:

            response = self._remote_runnable.invoke({"input": prompt, "chat_history": self._chat_history})

            # 只要能执行到这里，说明LLM运行成功，可能包括政策问题也通过了。
            response_content = cast(str, response['output'])
            self._handle_chat_history_on_request_success(prompt, response_content, option)
            logger.debug(f"\n{'=' * 50}\n{self._name} request result:\n{response_content}\n{'=' * 50}")
            return response_content
           
        except Exception as e:
            logger.error(f"{self._name}: request error: {e}")
            return None      

        return None
################################################################################################################################################################################
    async def async_request(self, prompt: str, option: AddChatHistoryOptionOnRequestSuccess) -> Optional[str]:
        
        if self._remote_runnable is None:
            logger.error(f"async_request: {self._name} have no agent.请确认是默认玩家，否则检查game_settings.json中配置。")
            return None
        
        try:

            response = await self._remote_runnable.ainvoke({"input": prompt, "chat_history": self._chat_history})

            # 只要能执行到这里，说明LLM运行成功，可能包括政策问题也通过了。
            response_content = cast(str, response['output'])
            self._handle_chat_history_on_request_success(prompt, response_content, option)
            logger.debug(f"\n{'=' * 50}\n{self._name} request result:\n{response_content}\n{'=' * 50}")
            return response_content
        
        except Exception as e:
            logger.error(f"{self._name}: request error: {e}")
            return None
        
        return None
################################################################################################################################################################################


class LangServeAgentSystem:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._agents: Dict[str, LangServeAgent] = {}
        self._request_tasks: Dict[str, tuple[str, AddChatHistoryOptionOnRequestSuccess]] = {}
        self._runtime_dir: Optional[Path] = None
################################################################################################################################################################################
    ### 必须设置根部的执行路行
    def set_runtime_dir(self, runtime_dir: Path) -> None:
        assert runtime_dir is not None
        self._runtime_dir = runtime_dir
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        assert runtime_dir.exists()
        assert self._runtime_dir.is_dir(), f"Directory is not a directory: {self._runtime_dir}"
################################################################################################################################################################################
    def register_agent(self, name: str, url: str) -> None:
        self._agents[name] = LangServeAgent(name, url)
################################################################################################################################################################################
    def connect_agent(self, name: str) -> bool:
        if name in self._agents:
            return self._agents[name].connect()
        logger.error(f"connect_actor_agent: {name} is not registered.")
        return False
################################################################################################################################################################################
    def agent_request(self, name: str, prompt: str, option: AddChatHistoryOptionOnRequestSuccess = AddChatHistoryOptionOnRequestSuccess.ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY) -> Optional[str]:
        if name in self._agents:
            return self._agents[name].request(prompt, option)
        logger.error(f"request: {name} is not registered.")
        return None
################################################################################################################################################################################
    def add_human_message_to_chat_history(self, name: str, chat: str) -> None:
        if name in self._agents:
            self._agents[name]._chat_history.extend([HumanMessage(content = chat)])
        else:
            logger.error(f"add_chat_history: {name} is not registered.")
################################################################################################################################################################################
    def add_ai_message_to_chat_history(self, name: str, chat: str) -> None:
        if name in self._agents:
            self._agents[name]._chat_history.extend([AIMessage(content = chat)])
        else:
            logger.error(f"add_chat_history: {name} is not registered.")
################################################################################################################################################################################
    def remove_last_conversation_between_human_and_ai(self, name: str) -> None:
        if not name in self._agents:
            return
        
        chat_history = self._agents[name]._chat_history
        if len(chat_history) == 0:
            return

        if isinstance(chat_history[-1], AIMessage):
            ## 是AI的回答，需要删除AI的回答和人的问题
            chat_history.pop()
        else:
            ## 最后一次不是AI的回答，就跳出，因为可能是有问题的。ai还没有回答，只有人的问题
            return

        ## 删除人的问题，直到又碰见AI的回答，就跳出        
        for i in range(len(chat_history)-1, -1, -1):
            if isinstance(chat_history[i], HumanMessage):
                chat_history.pop(i)
            elif isinstance(chat_history[i], AIMessage):
                break
################################################################################################################################################################################
    def chat_history_dump_path(self, who: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{who}"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"chat_history.json"
################################################################################################################################################################################  
    ### 所有的agent的chat history dump写入文件
    def dump_chat_history(self) -> None:
        for name in self._agents.keys():
            dump = self.create_chat_history_dump(name)
            if len(dump) == 0:
                continue
            _str = json.dumps(dump, ensure_ascii = False)
            self.write_chat_history_dump(name, _str)
################################################################################################################################################################################  
    # 创建一个agent的所有chat history的数据结构
    def create_chat_history_dump(self, name: str) -> List[Dict[str, str]]:
        res: List[Dict[str, str]] = []
        if name not in self._agents:
            return res
        
        chat_history = self._agents[name]._chat_history
        for chat in chat_history:
            if isinstance(chat, HumanMessage):
                res.append({"HumanMessage": cast(str, chat.content)})
            elif isinstance(chat, AIMessage):
                res.append({"AIMessage": cast(str, chat.content)})

        return res
################################################################################################################################################################################
    ##强制写入
    def write_chat_history_dump(self, who: str, content: str) -> None:
        path = self.chat_history_dump_path(who)
        try:
            res = path.write_text(content, encoding='utf-8')
        except Exception as e:
            logger.error(f"[{who}]写入chat history dump失败。{e}")
            return
################################################################################################################################################################################
    # 每个Agent需要异步请求调用的时候，需要先添加任务，然后全部异步任务添加完毕后，再调用run_async_requet_tasks
    def add_request_task(self, name: str, prompt: str, option: AddChatHistoryOptionOnRequestSuccess = AddChatHistoryOptionOnRequestSuccess.ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY) -> None:
        logger.debug(f"{name}添加异步请求任务:{prompt}")
        assert self._request_tasks.get(name, None) is None
        self._request_tasks[name] = (prompt, option)
################################################################################################################################################################################
    async def async_request(self, name: str, prompt: str, option: AddChatHistoryOptionOnRequestSuccess = AddChatHistoryOptionOnRequestSuccess.ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY) -> tuple[str, Optional[str], str]:
        if name in self._agents:
            response = await self._agents[name].async_request(prompt, option)
            return (name, response, prompt)
        logger.error(f"async_requet: {name} is not registered.")
        return (name, None, prompt)
################################################################################################################################################################################
    async def gather(self) -> List[tuple[str, Optional[str], str]]:
        tasks = [self.async_request(name, tp[0], tp[1]) for name, tp in self._request_tasks.items()]
        future = await asyncio.gather(*tasks)
        return future
################################################################################################################################################################################
    # 当确定全部异步请求任务添加完毕后，调用这个方法，等待所有任务完成，并拿到任务结果
    async def request_tasks(self, debug_tag: str = "") -> tuple[Dict[str, Optional[str]], Dict[str, str]]:

        result_responses: Dict[str, Optional[str]] = {}
        result_prompts: Dict[str, str] = {}

        start_time = time.time()

        # 调用async_gather，等待所有任务完成，并拿到任务结果
        async_results: List[tuple[str, Optional[str], str]] = await self.gather()
        if len(async_results) == 0:
            logger.debug(f"{debug_tag} run_async_requet_tasks no async_results.")
            return (result_responses, result_prompts)

        for result in async_results:
            name = result[0]
            result_responses[name] = result[1]
            result_prompts[name] = result[2]

        self._request_tasks.clear()

        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"{debug_tag} run_async_requet_tasks time: {execution_time:.2f} seconds")

        return (result_responses, result_prompts)
################################################################################################################################################################################
    # 从chat history中排除指定的内容
    def exclude_content_then_rebuild_chat_history(self, name: str, excluded_content: Set[str]) -> None:
        if not name in self._agents or len(excluded_content) == 0:
            return
        
        rebuild: List[HumanMessage | AIMessage] = []
        chat_history = self._agents[name]._chat_history
        for message in chat_history:
            if not self.message_has_content(cast(str, message.content), excluded_content):
                rebuild.append(message)

        self._agents[name]._chat_history = rebuild
################################################################################################################################################################################
    def create_filter_chat_history(self, name: str, check_content: Set[str]) -> List[str]:
        result: List[str] = []
        if not name in self._agents or len(check_content) == 0:
            return []
        chat_history = self._agents[name]._chat_history
        for message in chat_history:
            if self.message_has_content(cast(str, message.content), check_content):
                result.append(cast(str, message.content))
        return result
################################################################################################################################################################################
    # 替换chat history中的内容
    def replace_chat_history(self, name: str, replace_data: Dict[str, str]) -> None:
        if not name in self._agents:
            return
        chat_history = self._agents[name]._chat_history
        for message in chat_history:
            for key, value in replace_data.items():
                if key in cast(str, message.content):
                    message.content = value
################################################################################################################################################################################
    # 判断是否包含指定的内容
    def message_has_content(self, check_message: str, excluded_content: Set[str]) -> bool:
        for content in excluded_content:
            if content in check_message:
                return True
        return False
################################################################################################################################################################################