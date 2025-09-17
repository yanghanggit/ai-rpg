"""
MCP工具调用解析器模块

提供JSON格式工具调用的解析、验证功能
"""

import json
from typing import Any, Dict, List, Optional, Set
from loguru import logger

from .models import McpToolInfo


class ToolCallParser:
    """简化的工具调用解析器 - 仅支持JSON格式"""

    def __init__(self, available_tools: List[McpToolInfo]):
        self.available_tools = available_tools
        self.tool_names: Set[str] = {tool.name for tool in available_tools}

    def parse_tool_calls(self, content: str) -> List[Dict[str, Any]]:
        """
        解析工具调用，仅支持JSON格式

        Args:
            content: LLM响应内容

        Returns:
            List[Dict[str, Any]]: 解析出的工具调用列表
        """
        parsed_calls = []

        # 解析JSON格式的工具调用
        parsed_calls.extend(self._parse_json_format(content))

        # 去重和验证
        return self._deduplicate_and_validate(parsed_calls)

    def _parse_json_format(self, content: str) -> List[Dict[str, Any]]:
        """解析JSON格式的工具调用 - 仅支持标准格式"""
        calls = []

        # 查找所有可能的JSON对象
        # 首先寻找 "tool_call" 关键字的位置
        tool_call_positions = []
        start_pos = 0
        while True:
            pos = content.find('"tool_call"', start_pos)
            if pos == -1:
                break
            tool_call_positions.append(pos)
            start_pos = pos + 1

        # 对每个 "tool_call" 位置，尝试向前和向后查找完整的JSON对象
        for pos in tool_call_positions:
            # 向前查找最近的 {
            start_brace = content.rfind("{", 0, pos)
            if start_brace == -1:
                continue

            # 从 { 开始，使用括号匹配找到对应的 }
            brace_count = 0
            json_end = start_brace
            for i in range(start_brace, len(content)):
                if content[i] == "{":
                    brace_count += 1
                elif content[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

            if brace_count == 0:  # 找到了完整的JSON对象
                json_str = content[start_brace:json_end]
                try:
                    json_obj = json.loads(json_str)
                    call = self._json_to_tool_call(json_obj)
                    if call:
                        calls.append(call)
                except json.JSONDecodeError:
                    logger.warning(f"JSON格式错误，跳过此工具调用: {json_str}")
                    continue

        return calls

    def _json_to_tool_call(self, json_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """将JSON对象转换为工具调用 - 仅支持标准格式"""
        try:
            # 只支持标准格式: {"tool_call": {"name": "...", "arguments": {...}}}
            if "tool_call" not in json_obj:
                return None

            tool_call_obj = json_obj["tool_call"]
            tool_name = tool_call_obj.get("name")
            tool_args = tool_call_obj.get("arguments", {})

            if tool_name and tool_name in self.tool_names:
                return {
                    "name": tool_name,
                    "args": tool_args,
                }

        except Exception as e:
            logger.warning(f"JSON转换工具调用失败: {e}")

        return None

    def _deduplicate_and_validate(
        self, calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """去重和验证工具调用"""
        seen = set()
        unique_calls = []

        for call in calls:
            # 创建唯一标识
            call_id = (call["name"], json.dumps(call["args"], sort_keys=True))
            if call_id not in seen:
                seen.add(call_id)

                # 验证工具调用
                if self._validate_tool_call(call):
                    unique_calls.append(call)

        return unique_calls

    def _validate_tool_call(self, call: Dict[str, Any]) -> bool:
        """验证工具调用的有效性"""
        try:
            tool_name = call["name"]
            tool_args = call["args"]

            # 找到对应的工具
            tool_info = None
            for tool in self.available_tools:
                if tool.name == tool_name:
                    tool_info = tool
                    break

            if not tool_info:
                return False

            # 验证参数
            if tool_info.input_schema:
                required_params = tool_info.input_schema.get("required", [])
                for param in required_params:
                    if param not in tool_args:
                        logger.warning(f"工具 {tool_name} 缺少必需参数: {param}")
                        return False

            return True

        except Exception as e:
            logger.error(f"验证工具调用失败: {e}")
            return False
