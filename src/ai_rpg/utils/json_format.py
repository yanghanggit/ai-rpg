import json
import re
from typing import Any, Dict, Optional

from loguru import logger


def normalize_json_string(json_str: str) -> str:
    """清理JSON字符串，移除多余的空白字符。"""
    cleaned = json_str.strip()
    # 使用单个正则表达式替换所有空白字符
    return re.sub(r"\s+", "", cleaned)


def merge_json_fragments(json_str: str) -> Optional[Dict[str, Any]]:
    """
    合并多个JSON片段为单个JSON对象。

    Args:
        json_str: 包含多个JSON片段的字符串

    Returns:
        合并后的JSON对象，如果解析失败则返回None
    """
    try:
        cleaned_json_str = normalize_json_string(json_str)

        if not cleaned_json_str:
            return None

        # 尝试先解析整个字符串，如果成功就直接返回
        try:
            parsed = json.loads(cleaned_json_str)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass  # 继续尝试分割处理

        # 分割JSON片段
        json_fragments = re.split(r"}\s*{", cleaned_json_str)

        if len(json_fragments) == 1:
            # 只有一个片段，尝试直接解析
            try:
                parsed = json.loads(cleaned_json_str)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None

        # 修复片段格式
        fixed_fragments = []
        for i, fragment in enumerate(json_fragments):
            if i > 0 and not fragment.startswith("{"):
                fragment = "{" + fragment
            if i < len(json_fragments) - 1 and not fragment.endswith("}"):
                fragment = fragment + "}"
            fixed_fragments.append(fragment)

        # 解析JSON对象
        parsed_objects = []
        for fragment in fixed_fragments:
            try:
                parsed_obj = json.loads(fragment)
                if isinstance(parsed_obj, dict):
                    parsed_objects.append(parsed_obj)
                else:
                    logger.warning(f"Skipping non-dict JSON object: {type(parsed_obj)}")
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON fragment: {fragment[:100]}..., error: {e}"
                )
                continue

        if not parsed_objects:
            return None

        # 合并JSON对象
        combined_json: Dict[str, Any] = {}
        for obj in parsed_objects:
            for key, value in obj.items():
                if key in combined_json:
                    # 确保值为列表类型以便合并
                    if not isinstance(combined_json[key], list):
                        combined_json[key] = [combined_json[key]]

                    # 扩展列表
                    if isinstance(value, list):
                        combined_json[key].extend(value)
                    else:
                        combined_json[key].append(value)
                else:
                    combined_json[key] = value

        # 去重但保持顺序
        for key, value in combined_json.items():
            if isinstance(value, list):
                # 使用dict.fromkeys()保持顺序的同时去重
                combined_json[key] = list(dict.fromkeys(value))

        return combined_json

    except (json.JSONDecodeError, AttributeError) as e:
        logger.error(f"JSON parsing error in _combine_json_fragments: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in _combine_json_fragments: {e}")

    return None


def has_multiple_json_objects(json_response: str) -> bool:
    """检查JSON字符串是否包含多个片段。"""
    return len(re.split(r"}\s*{", json_response)) > 1
