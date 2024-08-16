from loguru import logger
from typing import Dict, List, Optional, Set, cast
from langchain_core.messages import HumanMessage, AIMessage
import json
from pathlib import Path
from my_agent.lang_serve_agent import LangServeAgent

class LangServeAgentSystem:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._agents: Dict[str, LangServeAgent] = {}
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
    def get_agent(self, name: str) -> Optional[LangServeAgent]:
        if name in self._agents:
            return self._agents[name]
        logger.error(f"get_actor_agent: {name} is not registered.")
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