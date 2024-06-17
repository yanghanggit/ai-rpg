from loguru import logger
from typing import Dict,  List, Union, Optional, Set, cast
from langchain_core.messages import HumanMessage, AIMessage
import json
import asyncio
import time
from langserve import RemoteRunnable  # type: ignore
from enum import Enum
from pathlib import Path

#
class AgentRequestOption(Enum):
    ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY = 1000,
    ADD_PROMPT_TO_CHAT_HISTORY = 2000
    DO_NOT_ADD_MESSAGE_TO_CHAT_HISTORY = 3000
  
#
class LangServeAgent:

    def __init__(self, name: str, url: str) -> None:
 
        self.name: str = name 
        self.url: str = url
        self.agent: RemoteRunnable = None
        self.chat_history: List[Union[HumanMessage, AIMessage]] = []
################################################################################################################################################################################
    def connect(self) -> bool:
        if self.url == "":
            logger.error(f"connect: {self.name} have no url. 请确认是默认玩家，否则检查game_settings.json中配置。")
            return False
        try:
            self.agent = RemoteRunnable(self.url)
            assert self.agent is not None
            self.chat_history = []
            return True
        except Exception as e:
            logger.error(e)
            return False        
        return False
################################################################################################################################################################################
    def __str__(self) -> str:
        return f"ActorAgent({self.name}, {self.url})"
################################################################################################################################################################################
    def _add_chat_history_after_response(self, prompt: str, reponse_content: str, option: AgentRequestOption) -> None:
        match(option):

            case AgentRequestOption.ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY:
                self.chat_history.extend([HumanMessage(content = prompt), AIMessage(content = reponse_content)])

            case AgentRequestOption.ADD_PROMPT_TO_CHAT_HISTORY:
                logger.debug(f"add_chat_history: {self.name} add prompt to chat history. 这是一种特殊情况的处理")
                self.chat_history.extend([HumanMessage(content = prompt)])

            case AgentRequestOption.DO_NOT_ADD_MESSAGE_TO_CHAT_HISTORY:
                logger.debug(f"add_chat_history: {self.name} do not add message to chat history.")

            case _:
                logger.error(f"add_chat_history: {self.name} option is not defined.")
################################################################################################################################################################################
    def request(self, prompt: str, option: AgentRequestOption) -> Optional[str]:

        if self.agent is None:
            logger.error(f"request: {self.name} have no agent.请确认是默认玩家，否则检查game_settings.json中配置。")
            return None
    
        try:

            response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
            response_content = cast(str, response.get('output', ''))
            self._add_chat_history_after_response(prompt, response_content, option)
            #self.chat_history.extend([HumanMessage(content = prompt), AIMessage(content = response_content)])
            logger.debug(f"\n{'=' * 50}\n{self.name} request result:\n{response_content}\n{'=' * 50}")
            return response_content
           
        except Exception as e:
            logger.error(f"{self.name}: request error: {e}")
            return None      

        return None
################################################################################################################################################################################
    async def a_request(self, prompt: str, option: AgentRequestOption) -> Optional[str]:
        
        if self.agent is None:
            logger.error(f"async_request: {self.name} have no agent.请确认是默认玩家，否则检查game_settings.json中配置。")
            return None
        
        try:

            response = await self.agent.ainvoke({"input": prompt, "chat_history": self.chat_history})
            response_content = cast(str, response.get('output', ''))
            self._add_chat_history_after_response(prompt, response_content, option)
            #self.chat_history.extend([HumanMessage(content = prompt), AIMessage(content = response_content)])
            logger.debug(f"\n{'=' * 50}\n{self.name} request result:\n{response_content}\n{'=' * 50}")
            return response_content
        
        except Exception as e:
            logger.error(f"{self.name}: request error: {e}")
            return None
        
        return None
################################################################################################################################################################################


class LangServeAgentSystem:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._agents: Dict[str, LangServeAgent] = {}
        self._async_request_tasks: Dict[str, tuple[str, AgentRequestOption]] = {}
        self._runtime_dir: Optional[Path] = None
############################################################################################################
    ### 必须设置根部的执行路行
    def set_runtime_dir(self, runtime_dir: Path) -> None:
        #
        assert runtime_dir is not None
        self._runtime_dir = runtime_dir
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        assert runtime_dir.exists()
        assert self._runtime_dir.is_dir(), f"Directory is not a directory: {self._runtime_dir}"
############################################################################################################
    def register_agent(self, name: str, url: str) -> None:
        self._agents[name] = LangServeAgent(name, url)
############################################################################################################
    def connect_agent(self, name: str) -> bool:
        if name in self._agents:
            return self._agents[name].connect()
        logger.error(f"connect_actor_agent: {name} is not registered.")
        return False
############################################################################################################
    def agent_request(self, name: str, prompt: str, option: AgentRequestOption = AgentRequestOption.ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY) -> Optional[str]:
        if name in self._agents:
            return self._agents[name].request(prompt, option)
        logger.error(f"request: {name} is not registered.")
        return None
############################################################################################################
    def add_human_message_to_chat_history(self, name: str, chat: str) -> None:
        if name in self._agents:
            self._agents[name].chat_history.extend([HumanMessage(content = chat)])
        else:
            logger.error(f"add_chat_history: {name} is not registered.")
############################################################################################################
    def add_ai_message_to_chat_history(self, name: str, chat: str) -> None:
        if name in self._agents:
            self._agents[name].chat_history.extend([AIMessage(content = chat)])
            #logger.debug(f"add_chat_history: {name} is added chat history.")
        else:
            logger.error(f"add_chat_history: {name} is not registered.")
############################################################################################################
    def remove_last_conversation_between_human_and_ai(self, name: str) -> None:
        if not name in self._agents:
            return
        
        chat_history = self._agents[name].chat_history
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
############################################################################################################
    def chat_history_dump_path(self, who: str) -> Path:
        assert self._runtime_dir is not None
        dir = self._runtime_dir / f"{who}"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"chat_history.json"
############################################################################################################  
    ### 所有的chathistory
    def dump_chat_history(self) -> None:
        for who in self._agents.keys():
            chatlist = self.create_chat_history_dump(who)
            if len(chatlist) == 0:
                continue
            chat_json = json.dumps(chatlist, ensure_ascii = False)
            chat_string = str(chat_json)
            self.write_chat_history_dump(who, chat_string)
############################################################################################################  
    ### 准备dump
    def create_chat_history_dump(self, who: str) ->  List[str]:
        if who not in self._agents:
            return []
        chathistory = self._agents[who].chat_history
        chatlist: List[str] = []
        for chat in chathistory:
            if isinstance(chat, HumanMessage):
                chatlist.append(f"[HumanMessage]: {chat.content}")
            elif isinstance(chat, AIMessage):
                chatlist.append(f"[{who}]: {chat.content}")
        return chatlist
############################################################################################################
    ##强制写入
    def write_chat_history_dump(self, who: str, content: str) -> None:
        _dump_path_ = self.chat_history_dump_path(who)
        try:
            res = _dump_path_.write_text(content, encoding='utf-8')
            logger.debug(f"[{who}]写入chat history dump成功。res: {res}")
        except Exception as e:
            logger.error(f"[{who}]写入chat history dump失败。{e}")
            return
############################################################################################################
    # 每个Agent需要异步请求调用的时候，需要先添加任务，然后全部异步任务添加完毕后，再调用run_async_requet_tasks
    def add_async_request_task(self, name: str, prompt: str, option: AgentRequestOption = AgentRequestOption.ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY) -> None:
        logger.debug(f"{name}添加异步请求任务:{prompt}")
        self._async_request_tasks[name] = (prompt, option)
############################################################################################################
    async def async_agent_requet(self, name: str, prompt: str, option: AgentRequestOption = AgentRequestOption.ADD_RESPONSE_AND_PROMPT_TO_CHAT_HISTORY) -> tuple[str, Optional[str], str]:
        if name in self._agents:
            response = await self._agents[name].a_request(prompt, option)
            return (name, response, prompt)
        logger.error(f"async_requet: {name} is not registered.")
        return (name, None, prompt)
############################################################################################################
    async def async_gather(self) -> List[tuple[str, Optional[str], str]]:
        tasks = [self.async_agent_requet(name, tp[0], tp[1]) for name, tp in self._async_request_tasks.items()]
        future = await asyncio.gather(*tasks)
        return future
############################################################################################################
    # 当确定全部异步请求任务添加完毕后，调用这个方法，等待所有任务完成，并拿到任务结果
    async def run_async_requet_tasks(self, tag: str = "") -> tuple[Dict[str, Optional[str]], Dict[str, str]]:

        start_time = time.time()

        # 调用async_gather，等待所有任务完成，并拿到任务结果
        async_results: List[tuple[str, Optional[str], str]] = await self.async_gather()

        response_dict: Dict[str, Optional[str]] = {}
        prompt_dict: Dict[str, str] = {}

        for result in async_results:
            response_dict[result[0]] = result[1]
            prompt_dict[result[0]] = result[2]

        self._async_request_tasks.clear()

        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"{tag} run_async_requet_tasks time: {execution_time:.2f} seconds")

        return (response_dict, prompt_dict)
############################################################################################################
    # 从chat history中排除指定的内容
    def exclude_chat_history(self, name: str, excluded_content: Set[str]) -> None:
        if not name in self._agents:
            return
        chat_history = self._agents[name].chat_history

        rebuild_chat_history: List[HumanMessage | AIMessage] = []
        for message in chat_history:
            if not self.check_message_has_tag(cast(str, message.content), excluded_content):
                rebuild_chat_history.append(message)

        self._agents[name].chat_history = rebuild_chat_history
############################################################################################################
    # 替换chat history中的内容
    def replace_chat_history(self, name: str, replace_data: Dict[str, str]) -> None:
        if not name in self._agents:
            return
        chat_history = self._agents[name].chat_history
        for message in chat_history:
            for key, value in replace_data.items():
                if key in cast(str, message.content):
                    message.content = value
############################################################################################################
    # 判断是否包含指定的内容
    def check_message_has_tag(self, check_message: str, excluded_content: Set[str]) -> bool:
        for tag in excluded_content:
            if tag in check_message:
                return True
        return False
############################################################################################################