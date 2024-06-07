from typing import List, Dict, Any, Optional, cast
import json
from loguru import logger
import re

############################################################################################################
## 当LLM穿回来的json是重复的错误的时候，可以尝试做合并处理
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
############################################################################################################
## 检查是否是“当LLM穿回来的json是重复的错误的时候，可以尝试做合并处理”
def is_repeat_error_json(errorjson: str) -> bool:
    json_parts = re.split(r'}\s*{', errorjson)
    return len(json_parts) > 1
############################################################################################################
## 是否是MD的JSON块
def is_markdown_json_block(md_json_block: str) -> bool:
    return "```json" in md_json_block
############################################################################################################
## 提取MD的JSON块内容
def extract_markdown_json_block_content(jsonblock: str) -> str:
    if "```json" in jsonblock:
        copyvalue = str(jsonblock).strip()
        copyvalue = copyvalue.replace("```json", "").replace("```", "").strip()
        return copyvalue
    
    return jsonblock
############################################################################################################
# TEST_ERROR_REPEAT_JSON = f"""
# {{
#     "PerceptionActionComponent": ["灰颜墓地"],
#     "SpeakActionComponent": ["@哈哈哈哈哈>啦啦啦啦"],
#     "CheckStatusActionComponent": ["埃利亚斯·格雷"],
#     "TagActionComponent": ["守墓人", "阴郁", "畸形"]
# }}
# {{
#     "PerceptionActionComponent": ["灰颜墓地"],
#     "BroadcastActionComponent": ["哈哈哈哈哈"],
#     "CheckStatusActionComponent": ["埃利亚斯·格雷"]
# }}"""
# # 测试代码
# if is_repeat_error_json(TEST_ERROR_REPEAT_JSON):
#     jjj = merge_json(TEST_ERROR_REPEAT_JSON)
#     logger.debug(jjj)