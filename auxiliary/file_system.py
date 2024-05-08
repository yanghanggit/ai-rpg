from loguru import logger
import os
from typing import Dict, List, Optional
from auxiliary.file_def import PropFile, KnownNPCFile, KnownStageFile, UseItemFile

class FileSystem:

    def __init__(self, name: str) -> None:
        self.name = name
        self.rootpath = ""
        # 拥有的道具
        self.propfiles: Dict[str, List[PropFile]] = {}
        # 知晓的NPC 
        self.known_npc_files: Dict[str, List[KnownNPCFile]] = {}
        # 知晓的Stage
        self.known_stage_files: Dict[str, List[KnownStageFile]] = {}
        # 由使用道具而产生的新文件
        self.use_item_files: Dict[str, List[UseItemFile]] = {}
################################################################################################################
    ### 必须设置根部的执行路行
    def set_root_path(self, rootpath: str) -> None:
        if self.rootpath != "":
            raise Exception(f"[filesystem]已经设置了根路径，不能重复设置。")
        self.rootpath = rootpath
        #logger.debug(f"[filesystem]设置了根路径为{rootpath}")
################################################################################################################
    ### 删除
    def deletefile(self, filepath: str) -> None:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.error(f"[{filepath}]的文件删除失败。")
            return
################################################################################################################
    def writefile(self, filepath: str, content: str) -> None:
        try:
            if not os.path.exists(filepath):
                os.makedirs(os.path.dirname(filepath), exist_ok=True) # 没有就先创建一个！
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        except FileNotFoundError as e:
            logger.error(f"[{filepath}]的文件不存在。")
            return
        except Exception as e:
            logger.error(f"[{filepath}]的文件写入失败。")
            return
################################################################################################################









    """
    道具相关的处理!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    """
    def prop_file_name(self, ownersname: str, filename: str) -> str:
        return f"{self.rootpath}{ownersname}/props/{filename}.json"
################################################################################################################
    ## 写一个道具的文件
    def write_prop_file(self, propfile: PropFile) -> None:
        self.deletefile(self.prop_file_name(propfile.ownersname, propfile.name))
        content = propfile.content()
        self.writefile(self.prop_file_name(propfile.ownersname, propfile.name), content)
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
        self.deletefile(self.prop_file_name(from_owner, propname))
        self.add_prop_file(PropFile(propname, to_owner, findownersfile.prop))
################################################################################################################
       




    """
    知道的NPC相关的处理!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    """
    def npc_file_name(self, ownersname: str, filename: str) -> str:
        return f"{self.rootpath}{ownersname}/npcs/{filename}.json"
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
    def get_known_npc_file(self, ownersname: str, npcname: str) -> Optional[KnownNPCFile]:
        npclist = self.known_npc_files.get(ownersname, [])
        for file in npclist:
            if file.npcsname == npcname:
                return file
        return None
################################################################################################################
    ## 写一个道具的文件
    def write_known_npc_file(self, known_npc_file: KnownNPCFile) -> None:
        ## 测试
        self.deletefile(self.npc_file_name(known_npc_file.ownersname, known_npc_file.name))
        content = known_npc_file.content()
        self.writefile(self.npc_file_name(known_npc_file.ownersname, known_npc_file.name), content)
################################################################################################################




    """
    知道的Stage相关的处理!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    """
    def stage_file_name(self, ownersname: str, filename: str) -> str:
        return f"{self.rootpath}{ownersname}/stages/{filename}.json"
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
        self.deletefile(self.stage_file_name(known_stage_file.ownersname, known_stage_file.name))
        content = known_stage_file.content()
        self.writefile(self.stage_file_name(known_stage_file.ownersname, known_stage_file.name), content)
################################################################################################################
    def get_known_stage_file(self, ownersname: str, stagename: str) -> Optional[KnownStageFile]:
        stagelist = self.known_stage_files.get(ownersname, [])
        for file in stagelist:
            if file.stagename == stagename:
                return file
        return None
################################################################################################################
    def use_item_to_target_file_name(self, ownersname: str, filename: str) -> str:
        return f"{self.rootpath}{ownersname}/items/{filename}.json"
    
    def has_item_to_target_file(self, ownersname: str, itemname: str) -> bool:
        return self.get_item_to_target_file(ownersname, itemname) is not None
    
    def get_item_to_target_files(self, ownersname: str) -> list[UseItemFile]:
        return self.use_item_files.get(ownersname, [])
    
    def get_item_to_target_file(self, ownersname: str, itemname: str) -> Optional[UseItemFile]:
        for file in self.get_item_to_target_files(ownersname):
            if file.name == itemname:
                return file
        return None
    
    def write_use_item_to_target_file(self, use_item_file: UseItemFile) -> None:
        self.deletefile(self.use_item_to_target_file_name(use_item_file.ownersname, use_item_file.name))
        content = use_item_file.content()
        self.writefile(self.use_item_to_target_file_name(use_item_file.ownersname, use_item_file.name), content)

    def add_use_item_to_target_file(self, use_item_file: UseItemFile) -> None:
        uselist = self.use_item_files.setdefault(use_item_file.ownersname, [])
        uselist.append(use_item_file)
        self.write_use_item_to_target_file(use_item_file)