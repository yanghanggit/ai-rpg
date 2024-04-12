from auxiliary.base_data import PropData, NPCData
from loguru import logger
import os
import json
from typing import Dict, List, Optional, Set

############################################################################################################
class BaseFile:
    def __init__(self, name: str, ownersname: str) -> None:
        self.name = name
        self.ownersname = ownersname

    def content(self) -> str:
        return ""
############################################################################################################
## 表达一个道具
class PropFile(BaseFile):
    def __init__(self, name: str, ownersname: str, prop: PropData) -> None:
        super().__init__(name, ownersname)
        self.prop = prop

    def content(self) -> str:
        prop_json = json.dumps(self.prop.__dict__, ensure_ascii = False)
        return prop_json
    
    def __str__(self) -> str:
        return f"{self.prop}"
    
############################################################################################################
## 表达一个NPC档案
class KnownNPCFile(BaseFile):
    def __init__(self, name: str, ownersname: str, npcname: str) -> None:
        super().__init__(name, ownersname)
        self.npcsname = npcname

    def content(self) -> str:
        jsonstr = f"{self.npcsname}: I know {self.npcsname}"
        return json.dumps(jsonstr, ensure_ascii = False)
    
    def __str__(self) -> str:
        return f"{self.npcsname}"
############################################################################################################
## 表达一个Stage的档案
class KnownStageFile(BaseFile):
    def __init__(self, name: str, ownersname: str, stagename: str) -> None:
        super().__init__(name, ownersname)
        self.stagename = stagename

    def content(self) -> str:
        jsonstr = f"{self.stagename}: I know {self.stagename}"
        return json.dumps(jsonstr, ensure_ascii = False)
    
    def __str__(self) -> str:
        return f"{self.stagename}"
############################################################################################################
class FileSystem:

    def __init__(self, name: str) -> None:
        self.name = name
        self.rootpath = ""

        # 拥有的道具
        self.propfiles: Dict[str, List[PropFile]] = {}

        # 知晓的NPC 
        self.known_npc_files: Dict[str, List[KnownNPCFile]] = {}
        self.known_stage_files: Dict[str, List[KnownStageFile]] = {}
    ############################################################################################################
    ### 必须设置根部的执行路行
    def set_root_path(self, rootpath: str) -> None:
        if self.rootpath != "":
            raise Exception(f"[filesystem]已经设置了根路径，不能重复设置。")
        self.rootpath = rootpath
        logger.debug(f"[filesystem]设置了根路径为{rootpath}")
    ############################################################################################################
    ## 测试的名字
    def filename(self, ownersname: str, filename: str) -> str:
        return f"{self.rootpath}{ownersname}/files/{filename}.json"
    ############################################################################################################
    ### 删除
    def deletefile(self, ownersname: str, filename: str) -> None:
        filepath = self.filename(ownersname, filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.error(f"[{ownersname}]的文件{filename}删除失败。")
            return
    ############################################################################################################   
    ## 写文件
    def writlefile(self, ownersname: str, filename: str, content: str) -> None:
        filepath = self.filename(ownersname, filename)
        logger.debug(f"[{ownersname}]的文件路径为 = [{filepath}]")
        try:
            # 没有就先创建一个！
            if not os.path.exists(filepath):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        except FileNotFoundError as e:
            logger.error(f"[{ownersname}]的文件不存在。")
            return
        except Exception as e:
            logger.error(f"[{ownersname}]的文件写入失败。")
            return
    ################################################################################################################
    ## 写一个道具的文件
    def write_prop_file(self, propfile: PropFile) -> None:
        ## 测试
        self.deletefile(propfile.ownersname, propfile.name)
        content = propfile.content()
        self.writlefile(propfile.ownersname, propfile.name, content)
    ################################################################################################################
    ## 添加一个道具文件
    def add_prop_file(self, propfile: PropFile) -> None:
        self.propfiles.setdefault(propfile.ownersname, []).append(propfile)
        self.write_prop_file(propfile)
    ################################################################################################################
    def get_prop_files(self, ownersname: str) -> List[PropFile]:
        return self.propfiles.get(ownersname, [])
    ################################################################################################################
    def get_prop_file(self, ownersname: str, propname: str) -> Optional[PropFile]:
        propfiles = self.get_prop_files(ownersname)
        for file in propfiles:
            if file.name == propname:
                return file
        return None
    ################################################################################################################
    def has_prop_file(self, ownersname: str, propname: str) -> bool:
        return self.get_prop_file(ownersname, propname) is not None
    ################################################################################################################
    def exchange_prop_file(self, from_owner: str, to_owner: str, propname: str) -> None:
        findownersfile = self.get_prop_file(from_owner, propname)
        if findownersfile is None:
            logger.error(f"{from_owner}没有{propname}这个道具。")
            return
        # 文件得从管理数据结构中移除掉
        self.propfiles[from_owner].remove(findownersfile)
        # 文件重新写入
        self.deletefile(from_owner, propname)
        self.add_prop_file(PropFile(propname, to_owner, findownersfile.prop))
    ################################################################################################################
       






    ################################################################################################################
    ## 添加一个你知道的NPC
    def add_known_npc_file(self, known_npc_file: KnownNPCFile) -> None:
        npclist = self.known_npc_files.setdefault(known_npc_file.ownersname, [])
        for file in npclist:
            if file.npcsname == known_npc_file.npcsname:
                # 名字匹配，先返回，不添加。后续可以复杂一些
                return
        npclist.append(known_npc_file)
        self.write_known_npc_file(known_npc_file) 
    ################################################################################################################
    ## 写一个道具的文件
    def write_known_npc_file(self, known_npc_file: KnownNPCFile) -> None:
        ## 测试
        self.deletefile(known_npc_file.ownersname, known_npc_file.name)
        content = known_npc_file.content()
        self.writlefile(known_npc_file.ownersname, known_npc_file.name, content)
    ################################################################################################################



    ################################################################################################################
    def add_known_stage_file(self, known_stage_file: KnownStageFile) -> None:
        stagelist = self.known_stage_files.setdefault(known_stage_file.ownersname, [])
        for file in stagelist:
            if file.stagename == known_stage_file.stagename:
                # 名字匹配，先返回，不添加。后续可以复杂一些
                return
        stagelist.append(known_stage_file)
        self.write_known_stage_file(known_stage_file)
    ################################################################################################################
    def write_known_stage_file(self, known_stage_file: KnownStageFile) -> None:
        ## 测试
        self.deletefile(known_stage_file.ownersname, known_stage_file.name)
        content = known_stage_file.content()
        self.writlefile(known_stage_file.ownersname, known_stage_file.name, content)
    ################################################################################################################