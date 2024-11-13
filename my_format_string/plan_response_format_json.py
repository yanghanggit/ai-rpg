from typing import List, Dict, Any, Optional, cast
import json
import re


############################################################################################################
## 当LLM穿回来的json是重复的错误的时候，可以尝试做合并处理
def _merge(json_str: str) -> Optional[Dict[str, List[str]]]:

    try:
        # 清理干净
        _copy = str(json_str).strip()
        _copy = _copy.replace("\n", "")
        _copy = _copy.replace("\t", "")
        _copy = re.sub(r"\s+", "", _copy)

        # 分割与重组
        json_parts = re.split(r"}\s*{", _copy)
        json_parts = [
            part + "}" if not part.endswith("}") else part for part in json_parts
        ]
        json_parts = [
            "{" + part if not part.startswith("{") else part for part in json_parts
        ]

        # 解析为JSON对象
        json_objects = [json.loads(part) for part in json_parts]

        # 合并这两个JSON对象
        merged_json: Any = {}
        for obj in json_objects:
            for key, value in obj.items():
                if key in merged_json:
                    if not isinstance(merged_json[key], list):
                        merged_json[key] = [merged_json[key]]
                    merged_json[key].extend(
                        value if isinstance(value, list) else [value]
                    )
                else:
                    merged_json[key] = value

        # 将所有值转换为唯一列表
        for key in merged_json:
            if isinstance(merged_json[key], list):
                merged_json[key] = list(set(merged_json[key]))

        return cast(Dict[str, List[str]], merged_json)

    except Exception as e:
        pass

    return None


############################################################################################################
## 检查是否是“当LLM穿回来的json是重复的错误的时候，可以尝试做合并处理”
def _is_repeat(errorjson: str) -> bool:
    json_parts = re.split(r"}\s*{", errorjson)
    return len(json_parts) > 1


############################################################################################################
## 是否是MD的JSON块
def _has_json_block(mark_down_content: str) -> bool:
    return "```json" in mark_down_content


############################################################################################################
## 提取MD的JSON块内容
def _extract_json_block(mark_down_content: str) -> str:

    if "```json" in mark_down_content:
        copyvalue = str(mark_down_content).strip()
        copyvalue = copyvalue.replace("```json", "").replace("```", "").strip()
        return copyvalue

    return mark_down_content


############################################################################################################


class PlanResponseFormatJSON:

    def __init__(self, input_str: str) -> None:
        self._input: str = str(input_str)
        self._output: str = str(input_str)

    ############################################################################################################
    def extract_json_block(self) -> "PlanResponseFormatJSON":
        if _has_json_block(self._output):
            self._output = _extract_json_block(self._output)
        return self

    ############################################################################################################
    def merge_repeat(self) -> "PlanResponseFormatJSON":
        if _is_repeat(self._output):
            merge_res = _merge(self._output)
            if merge_res is not None:
                self._output = json.dumps(merge_res, ensure_ascii=False)
        return self

    ############################################################################################################
    @property
    def output(self) -> str:
        return self._output

    ############################################################################################################
