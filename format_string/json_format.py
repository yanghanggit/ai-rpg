from typing import List, Dict, Any, Optional, cast, final
import json
import re


############################################################################################################
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
def _contains_duplicate_segments(json_response: str) -> bool:
    json_parts = re.split(r"}\s*{", json_response)
    return len(json_parts) > 1


############################################################################################################
def _contains_json_code(markdown_text: str) -> bool:
    return "```json" in markdown_text


############################################################################################################
def strip_json_code_block(markdown_text: str) -> str:

    if "```json" in markdown_text:
        copyvalue = str(markdown_text).strip()
        copyvalue = copyvalue.replace("```json", "").replace("```", "").strip()
        return copyvalue

    return markdown_text


############################################################################################################
############################################################################################################
############################################################################################################


@final
class JsonFormat:

    def __init__(self, source_string: str) -> None:
        self._source_string: str = str(source_string)
        self._formatted_output: str = str(source_string)

    ############################################################################################################
    @property
    def source_string(self) -> str:
        return self._source_string

    ############################################################################################################
    @property
    def format_output(self) -> str:
        return self._formatted_output

    ############################################################################################################
    def strip_json_code(self) -> "JsonFormat":
        if _contains_json_code(self._formatted_output):
            self._formatted_output = strip_json_code_block(self._formatted_output)
        return self

    ############################################################################################################
    def combine_duplicate_fragments(self) -> "JsonFormat":
        if _contains_duplicate_segments(self._formatted_output):
            merged_json_fragments = _combine_json_fragments(self._formatted_output)
            if merged_json_fragments is not None:
                self._formatted_output = json.dumps(
                    merged_json_fragments, ensure_ascii=False
                )
        return self

    ############################################################################################################
