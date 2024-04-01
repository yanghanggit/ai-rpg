from auxiliary.components import BackpackComponent
from auxiliary.world_data_builder import Prop
from loguru import logger
import os
import json
from typing import Dict, List, Set

############################################################################################################
class BaseFile:
    def __init__(self, name: str, ownersname: str) -> None:
        self.name = name
        self.ownersname = ownersname

    def content(self) -> str:
        pass
############################################################################################################
## 表达一个道具
class PropFile(BaseFile):
    def __init__(self, name: str, ownersname: str, prop: Prop) -> None:
        super().__init__(name, ownersname)
        self.prop = prop

    def content(self) -> str:
        prop_json = json.dumps(self.prop.__dict__, ensure_ascii = False)
        return prop_json
############################################################################################################
class FileSystem:
    def __init__(self) -> None:
        self.backpack:dict[str, set[str]] = dict()
        self.rootpath = ""
        self.propfiles: Dict[str, List[PropFile]] = dict()
############################################################################################################
    def init_backpack_component(self, comp: BackpackComponent) -> None:
        self.backpack[comp.owner_name] = set()

    def get_backpack_contents(self, comp: BackpackComponent) -> set[str]:
        return self.backpack.get(comp.owner_name, set())

    def add_content_into_backpack(self, comp: BackpackComponent, item: str) -> None:
        self.backpack.setdefault(comp.owner_name, set()).add(item)

    def remove_from_backpack(self, comp: BackpackComponent, item: str) -> None:
        self.backpack.get(comp.owner_name, set()).remove(item)

    def clear_backpack(self, comp: BackpackComponent) -> None:
        self.backpack[comp.owner_name] = set()



    ############################################################################################################
    ### yanghang addd
    ### 必须设置根部的执行路行
    def set_root_path(self, rootpath: str) -> None:
        if self.rootpath != "":
            raise Exception(f"[{self.name}]已经设置了根路径，不能重复设置。")
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