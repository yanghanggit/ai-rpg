from loguru import logger
import os
from typing import Dict, Optional


####################################################################################################################################
## 第一次初始化的时候，会做读取来确定角色初始上下文（记忆）
class KickOffMemorySystem:
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.rootpath: str = ""
        self.kick_off_memories: Dict[str, str] = {}
####################################################################################################################################
    def set_root_path(self, rootpath: str) -> None:
        if self.rootpath != "":
            raise Exception(f"[{self.name}]已经设置了根路径，不能重复设置。")
        self.rootpath = rootpath
####################################################################################################################################
    def md_file_path(self, who: str) -> str:
        return f"{self.rootpath}{who}/mems/memory.md"
####################################################################################################################################
    def add_kick_off_memory(self, who: str, kick_off_memory_content: str) -> None:
        mempath = self.md_file_path(who)    
        try:
            if not os.path.exists(mempath):
                os.makedirs(os.path.dirname(mempath), exist_ok=True)
            with open(mempath, "w", encoding="utf-8") as f:
                f.write(kick_off_memory_content)
                #self.initmemories[who] = initmemory #特殊记录
        except FileNotFoundError as e:
            return
        except Exception as e:
            return
        
        #初始化成功了
        mm = self.read_md(who)
        if mm is not None:
            self.kick_off_memories[who] = mm
####################################################################################################################################
    def read_md(self, who: str) -> Optional[str]:
        mempath = self.md_file_path(who)
        try:
            with open(mempath, "r", encoding="utf-8") as f:
                readmemory = f.read()
                return readmemory
        except FileNotFoundError as e:
            return None
        except Exception as e:
            return None
        return None
####################################################################################################################################
    def write_md(self, who: str, content: str) -> None:
        mempath = self.md_file_path(who)
        try:
            if not os.path.exists(mempath):
                os.makedirs(os.path.dirname(mempath), exist_ok=True)
            with open(mempath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            return
####################################################################################################################################
    def set_and_write(self, who: str, content: str) -> None:
        self.kick_off_memories[who] = content
        self.write_md(who, content)
####################################################################################################################################
    def get_kick_off_memory(self, who: str) -> str:
        return self.kick_off_memories.get(who, "")
####################################################################################################################################