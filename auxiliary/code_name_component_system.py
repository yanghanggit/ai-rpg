from loguru import logger
from typing import Dict, Optional, Any
from collections import namedtuple

####
class CodeNameComponentSystem:
    #
    def __init__(self, name: str) -> None:
        self.name = name
        self.name2codename: Dict[str, str] = {}
        self.codename2component: Dict[str, Any] = {}
    #
    def register_code_name_component_class(self, name: str, codename: str) -> None:
        #logger.warning(f"[{self.name}]注册了一个codename组件，name={name}, codename={codename}")
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
       
       
        