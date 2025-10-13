from typing import Dict, Tuple, List


def format_dict_as_markdown_list(data: Dict[str, str]) -> str:
    """清理JSON字符串，移除多余的空白字符。"""
    return "\n".join([f"- **{key}**: {value}" for key, value in data.items()])


def format_list_as_markdown_list(data: List[Tuple[str, str]]) -> str:
    """将列表格式化为Markdown列表"""
    return "\n".join([f"- **{item[0]}**: {item[1]}" for item in data])
