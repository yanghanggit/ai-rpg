from typing import Dict


def format_dict_as_markdown_list(data: Dict[str, str]) -> str:
    """清理JSON字符串，移除多余的空白字符。"""
    # cleaned = json_str.strip()
    # # 使用单个正则表达式替换所有空白字符
    # return re.sub(r"\s+", "", cleaned)

    return "\n".join([f"- **{key}**: {value}" for key, value in data.items()])
