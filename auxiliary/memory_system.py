from loguru import logger
import os
from typing import Dict, Optional

## 所有的初始记忆在这里管理, 目前是测试阶段因为就用一个md来存储是有问题的，后续会改进，比如按着时间来存储并加入数据库？
####################################################################################################################################
class MemorySystem:
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.rootpath: str = ""
        self.initmemories: Dict[str, str] = {}
        self.memories: Dict[str, str] = {}
####################################################################################################################################
    def set_root_path(self, rootpath: str) -> None:
        if self.rootpath != "":
            raise Exception(f"[{self.name}]已经设置了根路径，不能重复设置。")
        self.rootpath = rootpath
        logger.debug(f"[{self.name}]设置了根路径为{rootpath}")
####################################################################################################################################
    def memorymdfile(self, who: str) -> str:
        return f"{self.rootpath}{who}/mems/memory.md"
####################################################################################################################################
    #临时写法，后续会改，现在按着没有存档来的
    def initmemory(self, who: str, initmemory: str) -> None:
        mempath = self.memorymdfile(who)    
        try:
            if not os.path.exists(mempath):
                os.makedirs(os.path.dirname(mempath), exist_ok=True)
            with open(mempath, "w", encoding="utf-8") as f:
                f.write(initmemory)
                self.initmemories[who] = initmemory #特殊记录
        except FileNotFoundError as e:
            return
        except Exception as e:
            return
        
        #初始化成功了
        mm = self.readmemory(who)
        if mm is not None:
            self.memories[who] = mm
####################################################################################################################################
    def readmemory(self, who: str) -> Optional[str]:
        mempath = self.memorymdfile(who)
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
    def writememory(self, who: str, content: str) -> None:
        mempath = self.memorymdfile(who)
        try:
            if not os.path.exists(mempath):
                os.makedirs(os.path.dirname(mempath), exist_ok=True)
            with open(mempath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            return
####################################################################################################################################
    def set_and_write_memory(self, who: str, content: str) -> None:
        self.setmemory(who, content)
        self.writememory(who, content)
####################################################################################################################################
    def getmemory(self, who: str) -> str:
        return self.memories.get(who, "")
####################################################################################################################################
    def setmemory(self, who: str, content: str) -> None:
        self.memories[who] = content
####################################################################################################################################