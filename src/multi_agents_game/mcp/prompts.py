"""
MCP提示构建模块

提供工具描述和示例生成功能
"""

import json
from typing import Any, Dict
from loguru import logger

from .models import McpToolInfo


def build_json_tool_example(tool: McpToolInfo) -> str:
    """为工具构建JSON格式的调用示例 - 简化版本"""
    try:
        # 构建示例参数 - 只包含必需参数
        example_args: Dict[str, Any] = {}
        if tool.input_schema and "properties" in tool.input_schema:
            properties = tool.input_schema["properties"]
            required = tool.input_schema.get("required", [])

            # 只为必需参数生成示例值
            for param_name in required:
                if param_name in properties:
                    param_info = properties[param_name]
                    param_type = param_info.get("type", "string")

                    if param_type == "string":
                        example_args[param_name] = "示例值"
                    elif param_type == "integer":
                        example_args[param_name] = 1
                    elif param_type == "boolean":
                        example_args[param_name] = True
                    else:
                        example_args[param_name] = "示例值"

        # 构建JSON示例
        example_json = {"tool_call": {"name": tool.name, "arguments": example_args}}
        json_str = json.dumps(example_json, ensure_ascii=False)

        return f"调用 {tool.name} 的示例：\n```json\n{json_str}\n```"

    except Exception as e:
        logger.warning(f"构建JSON工具示例失败: {tool.name}, 错误: {e}")
        # 降级到简单示例
        simple_example = {"tool_call": {"name": tool.name, "arguments": {}}}
        json_str = json.dumps(simple_example, ensure_ascii=False)
        return f"调用 {tool.name} 的示例：\n```json\n{json_str}\n```"


def format_tool_description_simple(tool: McpToolInfo) -> str:
    """格式化单个工具的描述 - 简化版本"""
    try:
        # 基本工具信息
        tool_desc = f"- **{tool.name}**: {tool.description}"

        # 只显示必需参数
        if tool.input_schema and "properties" in tool.input_schema:
            required = tool.input_schema.get("required", [])
            if required:
                required_params = ", ".join(f"`{param}`" for param in required)
                tool_desc += f" (必需参数: {required_params})"

        return tool_desc

    except Exception as e:
        logger.warning(f"格式化工具描述失败: {tool.name}, 错误: {e}")
        return f"- **{tool.name}**: {tool.description}"
