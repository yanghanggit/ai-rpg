"""
MCP响应处理模块

提供工具调用结果的处理和响应合成功能
"""

import re
from typing import Any, Dict, List
from loguru import logger


def remove_tool_call_markers(content: str) -> str:
    """移除内容中的JSON格式工具调用标记 - 增强版"""
    # 查找所有 "tool_call" 的位置
    tool_call_positions = []
    start_pos = 0
    while True:
        pos = content.find('"tool_call"', start_pos)
        if pos == -1:
            break
        tool_call_positions.append(pos)
        start_pos = pos + 1

    # 从后往前删除，避免位置偏移
    for pos in reversed(tool_call_positions):
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
            # 检查是否确实包含 tool_call
            json_str = content[start_brace:json_end]
            if '"tool_call"' in json_str:
                # 删除整个JSON块，包括可能的markdown代码块标记
                # 查找是否在代码块中
                before_start = max(0, start_brace - 10)
                before_text = content[before_start:start_brace]
                after_end = min(len(content), json_end + 10)
                after_text = content[json_end:after_end]

                # 扩展删除范围以包含markdown代码块
                actual_start = start_brace
                actual_end = json_end

                if "```json" in before_text:
                    # 找到代码块开始
                    code_start = content.rfind("```json", before_start, start_brace)
                    if code_start != -1:
                        actual_start = code_start

                if "```" in after_text:
                    # 找到代码块结束
                    code_end = content.find("```", json_end, after_end)
                    if code_end != -1:
                        actual_end = code_end + 3

                # 执行删除
                content = content[:actual_start] + content[actual_end:]

    # 清理多余的空行和空的代码块
    content = re.sub(r"```json\s*```", "", content)  # 移除空的json代码块
    content = re.sub(r"```\s*```", "", content)  # 移除空的代码块
    content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content)  # 清理多余空行

    return content


def build_tool_results_section(tool_outputs: List[Dict[str, Any]]) -> str:
    """构建工具结果部分"""
    results = []

    for output in tool_outputs:
        tool_name = output.get("tool", "未知工具")
        success = output.get("success", False)
        result = output.get("result", "无结果")
        exec_time = output.get("execution_time", 0.0)

        if success:
            status_icon = "✅"
            status_text = "成功"
        else:
            status_icon = "❌"
            status_text = "失败"

        # 格式化执行时间
        time_text = f" ({exec_time:.1f}s)" if exec_time > 0 else ""

        # 构建结果文本
        result_text = (
            f"{status_icon} **{tool_name}** {status_text}{time_text}\n{result}"
        )
        results.append(result_text)

    return "\n\n".join(results)


def build_standalone_tool_response(tool_outputs: List[Dict[str, Any]]) -> str:
    """构建独立的工具响应（当原响应为空时）"""
    if len(tool_outputs) == 1:
        output = tool_outputs[0]
        tool_name = output.get("tool", "工具")
        success = output.get("success", False)
        result = output.get("result", "无结果")

        if success:
            return f"已为您执行{tool_name}，结果如下：\n\n{result}"
        else:
            return f"抱歉，执行{tool_name}时发生错误：\n\n{result}"
    else:
        successful_count = sum(
            1 for output in tool_outputs if output.get("success", False)
        )
        total_count = len(tool_outputs)

        intro = f"已执行 {total_count} 个工具，其中 {successful_count} 个成功：\n\n"
        results = build_tool_results_section(tool_outputs)

        return intro + results


def synthesize_response_with_tools(
    original_response: str,
    tool_outputs: List[Dict[str, Any]],
    parsed_tool_calls: List[Dict[str, Any]],
) -> str:
    """
    智能合成包含工具结果的响应

    Args:
        original_response: 原始LLM响应
        tool_outputs: 工具执行结果
        parsed_tool_calls: 解析的工具调用

    Returns:
        str: 合成后的响应内容
    """
    try:
        # 移除原始响应中的工具调用标记
        cleaned_response = remove_tool_call_markers(original_response)

        # 如果没有工具输出，直接返回清理后的响应
        if not tool_outputs:
            return cleaned_response.strip()

        # 构建工具结果部分
        tool_results_section = build_tool_results_section(tool_outputs)

        # 智能组合响应
        if cleaned_response.strip():
            # 如果原响应有内容，在其后添加工具结果
            synthesized = f"{cleaned_response.strip()}\n\n{tool_results_section}"
        else:
            # 如果原响应为空，只返回工具结果的友好描述
            synthesized = build_standalone_tool_response(tool_outputs)

        return synthesized.strip()

    except Exception as e:
        logger.error(f"响应合成失败: {e}")
        # 降级处理：简单拼接
        return f"{original_response}\n\n工具执行结果：\n{str(tool_outputs)}"
