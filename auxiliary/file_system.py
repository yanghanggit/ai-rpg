from auxiliary.base_data import PropData
from loguru import logger
import os
import json
from typing import Dict, List, Optional

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
    
### yh modified!!!!
class FileSystem:

    def __init__(self, name: str) -> None:
        self.name = name
        self.rootpath = ""
        self.propfiles: Dict[str, List[PropFile]] = {}
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
        return f"{self.rootpath}{ownersname}/{filename}.json"
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
       
        