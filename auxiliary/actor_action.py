from typing import List, Dict, Any, Optional, cast
import json
from loguru import logger
import re


TEST_ERROR_REPEAT_JSON = f"""
{{
    "PerceptionActionComponent": ["灰颜墓地"],
    "SpeakActionComponent": ["@哈哈哈哈哈>啦啦啦啦"],
    "CheckStatusActionComponent": ["埃利亚斯·格雷"],
    "TagActionComponent": ["守墓人", "阴郁", "畸形"]
}}
{{
    "PerceptionActionComponent": ["灰颜墓地"],
    "BroadcastActionComponent": ["哈哈哈哈哈"],
    "CheckStatusActionComponent": ["埃利亚斯·格雷"]
}}"""

def merge_json(json_str: str) -> Optional[Dict[str, List[str]]]:
    try:
        #清理干净
        _copy = str(json_str).strip()
        _copy = _copy.replace('\n', '')
        _copy = _copy.replace('\t', '')
        _copy = re.sub(r'\s+', '', _copy)

        #分割与重组
        json_parts = re.split(r'}\s*{', _copy)
        json_parts = [part + '}' if not part.endswith('}') else part for part in json_parts]
        json_parts = ['{' + part if not part.startswith('{') else part for part in json_parts]

        # 解析为JSON对象
        json_objects = [json.loads(part) for part in json_parts]

        # 合并这两个JSON对象
        merged_json: Any = {}
        for obj in json_objects:
            for key, value in obj.items():
                if key in merged_json:
                    if not isinstance(merged_json[key], list):
                        merged_json[key] = [merged_json[key]]
                    merged_json[key].extend(value if isinstance(value, list) else [value])
                else:
                    merged_json[key] = value

        # 将所有值转换为唯一列表
        for key in merged_json:
            if isinstance(merged_json[key], list):
                merged_json[key] = list(set(merged_json[key]))

        return cast(Dict[str, List[str]], merged_json) 
           
    except Exception as e:
        logger.error(f"merge_json_strings failed. {e}")
        return None
    return None   

## 检查是否是
def is_repeat_error_json(errorjson: str) -> bool:
    json_parts = re.split(r'}\s*{', errorjson)
    return len(json_parts) > 1

## 测试代码
if is_repeat_error_json(TEST_ERROR_REPEAT_JSON):
    jjj = merge_json(TEST_ERROR_REPEAT_JSON)
    #logger.debug(jjj)

## 是否是
def is_markdown_json_block(md_json_block: str) -> bool:
    return "```json" in md_json_block

## 处理
def extract_markdown_json_block_content(jsonblock: str) -> str:
    if "```json" in jsonblock:
        copyvalue = str(jsonblock).strip()
        copyvalue = copyvalue.replace("```json", "").replace("```", "").strip()
        return copyvalue
    
    return jsonblock

############################################################################################################
class ActorAction:
    def __init__(self, name: str = "", actionname: str = "", values: List[str] = []) -> None:
        self.name = name  
        self.actionname = actionname
        self.values = values
############################################################################################################
    def __str__(self) -> str:
        return f"ActorAction({self.name}, {self.actionname}, {self.values})"
############################################################################################################
    def __repr__(self) -> str:
        return f"ActorAction({self.name}, {self.actionname}, {self.values})"
############################################################################################################
    def single_value(self) -> str:
        if len(self.values) == 0:
            return ""
        return " ".join(self.values)
############################################################################################################





class ActorPlan:
    def __init__(self, name: str, raw_data: str) -> None:

        self.name: str = name  
        self.raw_data: str = raw_data
        self.json_data: Dict[str, List[str]] = {}
        self.actions: List[ActorAction] = []

        # 以防万一的检查
        self.json_content = self.handle_md_json_block_and_repeat_content(self.raw_data)

        #核心执行
        self.load_then_build() 

############################################################################################################
    def handle_md_json_block_and_repeat_content(self, raw_data: str) -> str:
        # step0: 不要改以前的。
        result = str(raw_data)

        #step1: GPT4 也有可能输出markdown json block。以防万一，我们检查一下。
        if is_markdown_json_block(result):
            logger.error(f"ActorPlan: has markdown json block {result}")
            result = extract_markdown_json_block_content(result)

        #step2: GPT4 也有可能输出重复的json。我们合并一下。有可能上面的json block的错误也犯了，所以放到第二个步骤来做
        if is_repeat_error_json(result):
            logger.error(f"ActorPlan: has repeat json {result}")
            merge_res = merge_json(result)
            if merge_res is not None:
                result = json.dumps(merge_res)

        # 有可能什么都不做，也有可能出现了错误进行了处理
        return result
############################################################################################################
    def load_then_build(self) -> None:
        try:
            json_data = json.loads(self.json_content)
            if not self.check_data_format(json_data):
                logger.error(f"[{self.name}] = ActorPlan, check_data_format error.")
                return
            
            self.json_data = json_data
            self.build(self.json_data)

        except Exception as e:
            logger.error(f"[{self.name}] = json.loads error.")
        return    
############################################################################################################
    def build(self, json: Dict[str, List[str]]) -> None:
        for key, value in json.items():
            action = ActorAction(self.name, key, value)
            self.actions.append(action)
############################################################################################################
    def check_data_format(self, json_data: Any) -> bool:
        for key, value in json_data.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False
        return True
############################################################################################################
    def __str__(self) -> str:
        return f"ActorPlan({self.name}, {self.raw_data})"
############################################################################################################
    def __repr__(self) -> str:
        return f"ActorPlan({self.name}, {self.raw_data})"
############################################################################################################