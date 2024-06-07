import os
from loguru import logger
from typing import Dict,  List, Union, Optional, Set, cast
from langchain_core.messages import HumanMessage, AIMessage
import json
import asyncio
import time
from langserve import RemoteRunnable  # type: ignore

class LangServeAgent:

    def __init__(self, name: str = "", url: str = "") -> None:
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
    def request(self, prompt: str) -> Optional[str]:

        if self.agent is None:
            logger.error(f"request: {self.name} have no agent.请确认是默认玩家，否则检查game_settings.json中配置。")
            return None
    
        try:

            response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
            responsecontent = cast(str, response.get('output', ''))
            self.chat_history.extend([HumanMessage(content = prompt), AIMessage(content = responsecontent)])
            logger.debug(f"\n{'=' * 50}\n{self.name} request result:\n{responsecontent}\n{'=' * 50}")
            return responsecontent
           
        except Exception as e:
            logger.error(f"{self.name}: request error: {e}")
            return None      

        return None
################################################################################################################################################################################
    async def a_request(self, prompt: str) -> Optional[str]:
        if self.agent is None:
            logger.error(f"async_request: {self.name} have no agent.请确认是默认玩家，否则检查game_settings.json中配置。")
            return None
        try:
            response = await self.agent.ainvoke({"input": prompt, "chat_history": self.chat_history})
            response_content = cast(str, response.get('output', ''))
            self.chat_history.extend([HumanMessage(content = prompt), AIMessage(content = response_content)])
            logger.debug(f"\n{'=' * 50}\n{self.name} request result:\n{response_content}\n{'=' * 50}")
            return response_content
        except Exception as e:
            logger.error(f"{self.name}: request error: {e}")
            return None
        return None
################################################################################################################################################################################


class LangServeAgentSystem:

    def __init__(self, name: str) -> None:
        self.name: str = name
        self._agents: Dict[str, LangServeAgent] = {}
        self.rootpath = ""
        self.async_request_tasks: Dict[str, str] = {}
############################################################################################################
    ### 必须设置根部的执行路行
    def set_root_path(self, rootpath: str) -> None:
        if self.rootpath != "":
            raise Exception(f"[filesystem]已经设置了根路径，不能重复设置。")
        self.rootpath = rootpath
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
    def agent_request(self, name: str, prompt: str) -> Optional[str]:
        if name in self._agents:
            return self._agents[name].request(prompt)
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
    def get_chat_history(self, name: str) -> List[Union[HumanMessage, AIMessage]]:
        if name in self._agents:
            return self._agents[name].chat_history
        logger.error(f"get_chat_history: {name} is not registered.")
        return []   
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
    ### 目标文件
    def chat_history_dump_path(self, who: str) -> str:
        return f"{self.rootpath}{who}/chat_history/dump.json"
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
        chathistory = self.get_chat_history(who)
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
        mempath = self.chat_history_dump_path(who)
        try:
            if not os.path.exists(mempath):
                os.makedirs(os.path.dirname(mempath), exist_ok=True)
            with open(mempath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"[{who}]写入chat history dump失败。")
            return
############################################################################################################
    # 每个Agent需要异步请求调用的时候，需要先添加任务，然后全部异步任务添加完毕后，再调用run_async_requet_tasks
    def add_async_request_task(self, name: str, prompt: str) -> None:
        logger.debug(f"{name}添加异步请求任务:{prompt}")
        self.async_request_tasks[name] = prompt
############################################################################################################
    async def async_agent_requet(self, name: str, prompt: str) -> tuple[str, Optional[str]]:
        if name in self._agents:
            response = await self._agents[name].a_request(prompt)
            return (name, response)
        logger.error(f"async_requet: {name} is not registered.")
        return (name, None)
############################################################################################################
    async def async_gather(self) -> list[tuple[str, Optional[str]]]:
        tasks = [self.async_agent_requet(name, prompt) for name, prompt in self.async_request_tasks.items()]
        response = await asyncio.gather(*tasks)
        return response
############################################################################################################
    # 当确定全部异步请求任务添加完毕后，调用这个方法，等待所有任务完成，并拿到任务结果
    async def run_async_requet_tasks(self, tag: str = "") -> dict[str, Optional[str]]:

        start_time = time.time()

        # 调用async_gather，等待所有任务完成，并拿到任务结果
        async_results: list[tuple[str, Optional[str]]] = await self.async_gather()

        response_dict: dict[str, Optional[str]] = {}
        for result in async_results:
            response_dict[result[0]] = result[1]

        self.async_request_tasks.clear()

        end_time = time.time()
        execution_time = end_time - start_time
        logger.debug(f"{tag} run_async_requet_tasks time: {execution_time:.2f} seconds")

        return response_dict
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
    # 最后的AI回复，需要从chat history中删除
    def remove_ai_message_from_chat_history(self, name: str, content: str) -> None:
        
        if not name in self._agents:
            return
        
        chat_history = self._agents[name].chat_history
        if len(chat_history) == 0:
            return
        
        # 重建chat_history，删除目标的AI回复
        chat_history = [message for message in chat_history if not (isinstance(message, AIMessage) and message.content == content)]
        
        # 这么写在并发的情况下，可能会出错。可能会抢最后一个回复。！！！！
        # last_message = chat_history[-1]
        # if isinstance(last_message, AIMessage):
        #     # tofix：出现过assert响的情况，加这个log用来下次出现时定位用
        #     logger.debug(f"name is{name} .content:{content} and last_message:{last_message.content}")
        #     assert content == last_message.content
        #     chat_history.pop()
############################################################################################################