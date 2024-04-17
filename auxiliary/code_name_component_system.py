from loguru import logger
from typing import Dict, Optional, Any
from collections import namedtuple

####
class CodeNameComponentSystem:
    #
    def __init__(self, name: str) -> None:
        self.name = name

        #方便快速查找任何知道名字或者codename的对象
        self.name2codename: Dict[str, str] = {}
        self.codename2component: Dict[str, Any] = {}

        #方便快速查找stage
        self.name2stagetag: Dict[str, str] = {}
        self.stagetag2component: Dict[str, Any] = {}

    #
    def register_code_name_component_class(self, name: str, codename: str) -> None:
        self.name2codename[name] = codename
        self.codename2component[codename] = namedtuple(codename, 'name')
    
    #
    def get_component_class_by_name(self, name: str) -> Optional[Any]:
        codename = self.name2codename.get(name, None)
        if codename is None:
            return None
        return self.codename2component.get(codename, None)
    
    #
    def get_component_class_by_code_name(self, codename: str) -> Optional[Any]:
        return self.codename2component.get(codename, None)
    
    #
    def register_stage_tag_component_class(self, stagename: str, stagecodename: str) -> None:
        stagetag = f"stagetag_{stagecodename}"
        #logger.warning(f"[{self.name}]注册了一个stagetag组件，stagename={stagename}, stagetag={stagetag}")
        self.name2stagetag[stagename] = stagetag
        self.stagetag2component[stagetag] = namedtuple(stagetag, 'name')

    #
    def get_stage_tag_component_class_by_name(self, stagename: str) -> Optional[Any]:
        stagetag = self.name2stagetag.get(stagename, None)
        if stagetag is None:
            return None
        return self.stagetag2component.get(stagetag, None)
       
       
        