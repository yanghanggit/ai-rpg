from typing import Dict, Tuple, List
import re


def format_dict_as_markdown_list(data: Dict[str, str]) -> str:
    """清理JSON字符串，移除多余的空白字符。"""
    return "\n".join([f"- **{key}**: {value}" for key, value in data.items()])


def format_list_as_markdown_list(data: List[Tuple[str, str]]) -> str:
    """将列表格式化为Markdown列表"""
    return "\n".join([f"- **{item[0]}**: {item[1]}" for item in data])


def has_json_code_block(markdown_text: str) -> bool:
    """检查文本是否包含JSON代码块标记。"""
    return "```json" in markdown_text.lower()


def extract_json_from_code_block(markdown_text: str) -> str:
    """
    从Markdown文本中提取JSON内容，移除代码块标记。

    Args:
        markdown_text: 可能包含JSON代码块的Markdown文本

    Returns:
        提取出的JSON字符串
    """
    if not has_json_code_block(markdown_text):
        return markdown_text

    # 使用正则表达式更精确地提取JSON内容
    pattern = r"```json\s*(.*?)\s*```"
    match = re.search(pattern, markdown_text, re.DOTALL | re.IGNORECASE)

    if match:
        return match.group(1).strip()

    # 回退到简单的字符串替换方法
    result = markdown_text.strip()
    result = re.sub(r"```json\s*", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s*```", "", result)
    return result.strip()
