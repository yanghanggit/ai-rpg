from typing import List, Dict, Any, Optional, cast
import json
import re


############################################################################################################
## 当LLM穿回来的json是重复的错误的时候，可以尝试做合并处理
def _combine_json_fragments(json_str: str) -> Optional[Dict[str, List[str]]]:

    try:
        # 清理干净
        cleaned_json_str = str(json_str).strip()
        cleaned_json_str = cleaned_json_str.replace("\n", "")
        cleaned_json_str = cleaned_json_str.replace("\t", "")
        cleaned_json_str = re.sub(r"\s+", "", cleaned_json_str)

        # 分割与重组
        json_fragments = re.split(r"}\s*{", cleaned_json_str)
        json_fragments = [
            part + "}" if not part.endswith("}") else part for part in json_fragments
        ]
        json_fragments = [
            "{" + part if not part.startswith("{") else part for part in json_fragments
        ]

        # 解析为JSON对象
        parsed_json_objects = [json.loads(part) for part in json_fragments]

        # 合并这两个JSON对象
        combined_json: Any = {}
        for obj in parsed_json_objects:
            for key, value in obj.items():
                if key in combined_json:
                    if not isinstance(combined_json[key], list):
                        combined_json[key] = [combined_json[key]]
                    combined_json[key].extend(
                        value if isinstance(value, list) else [value]
                    )
                else:
                    combined_json[key] = value

        # 将所有值转换为唯一列表
        for key in combined_json:
            if isinstance(combined_json[key], list):
                combined_json[key] = list(set(combined_json[key]))

        return cast(Dict[str, List[str]], combined_json)

    except Exception as e:
        pass

    return None


############################################################################################################
## 检查是否是“当LLM穿回来的json是重复的错误的时候，可以尝试做合并处理”
def _contains_duplicate_segments(json_response: str) -> bool:
    json_parts = re.split(r"}\s*{", json_response)
    return len(json_parts) > 1


############################################################################################################
## 是否是MD的JSON块
def _contains_json_code(markdown_text: str) -> bool:
    return "```json" in markdown_text


############################################################################################################
## 提取MD的JSON块内容
def _strip_json_code_block(markdown_text: str) -> str:

    if "```json" in markdown_text:
        copyvalue = str(markdown_text).strip()
        copyvalue = copyvalue.replace("```json", "").replace("```", "").strip()
        return copyvalue

    return markdown_text


############################################################################################################
############################################################################################################
############################################################################################################


class JsonPlanResponseHandler:

    def __init__(self, source_string: str) -> None:
        self._source_string: str = str(source_string)
        self._output: str = str(source_string)

    ############################################################################################################
    def strip_json_code(self) -> "JsonPlanResponseHandler":
        if _contains_json_code(self._output):
            self._output = _strip_json_code_block(self._output)
        return self

    ############################################################################################################
    def combine_duplicate_fragments(self) -> "JsonPlanResponseHandler":
        if _contains_duplicate_segments(self._output):
            merge_res = _combine_json_fragments(self._output)
            if merge_res is not None:
                self._output = json.dumps(merge_res, ensure_ascii=False)
        return self

    ############################################################################################################
    @property
    def output(self) -> str:
        return self._output

    ############################################################################################################
