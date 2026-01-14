"""
命令行参数解析工具模块

提供用于解析命令行风格输入的工具函数，支持 --key=value 格式的参数提取。
"""

from typing import Dict, Set
from loguru import logger


def parse_command_args(command_input: str, keys: Set[str]) -> Dict[str, str]:
    """
    从命令行风格的输入中提取指定的参数。

    解析格式为 --key=value 的命令行参数，支持提取多个参数。

    Args:
        command_input: 命令行输入字符串，如 "/speak --target=角色 --content=你好"
        keys: 需要提取的参数键集合

    Returns:
        包含提取参数的字典，只包含 keys 中指定且实际存在的参数

    Examples:
        >>> parse_command_args("/speak --target=角色 --content=你好", {"target", "content"})
        {'target': '角色', 'content': '你好'}

        >>> parse_command_args("/switch_stage --params=场景.营地", {"params"})
        {'params': '场景.营地'}

        >>> parse_command_args("/speak --target=", {"target", "content"})
        {}  # 空值会被过滤

    Note:
        - 使用 maxsplit=1 确保只在第一个等号处分割，支持值中包含等号
        - 自动过滤空值参数
        - 自动去除键和值的首尾空白字符
        - 只返回在 keys 集合中指定的参数
    """
    result: Dict[str, str] = {}

    try:
        # 按 "--" 分割，跳过第一个元素（通常是命令本身）
        parts = command_input.split("--")[1:]

        for part in parts:
            if "=" not in part:
                continue

            # 使用 maxsplit=1 确保只在第一个等号处分割
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()

            # 只提取指定的键，且值不为空
            if key in keys and value:
                result[key] = value

    except (ValueError, AttributeError) as e:
        logger.error(f"解析命令参数失败 - 输入: {command_input}, 错误: {e}")

    return result
