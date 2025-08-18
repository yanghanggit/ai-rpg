"""
MCP (Model Contfrom src.multi_agents_game.chat_services.chat_deepseek_mcp_graph import (
    McpState,
    create_sample_mcp_tools,
    execute_mcp_tool,
    McpToolWrapper
)otocol) 功能单元测试

测试 DeepSeek + MCP 集成的核心功能：
- MCP 工具创建和执行
- MCP 状态管理
- 工具参数处理和错误处理
"""

import pytest
import sys
import os
from typing import List, Dict, Any

# 添加 src 目录到路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src")
)

from src.multi_agents_game.chat_services.chat_deepseek_mcp_graph import (
    McpState,
    create_sample_mcp_tools,
    execute_mcp_tool,
    McpToolWrapper,
)


class TestMcpTools:
    """MCP 工具功能测试类"""

    @pytest.fixture
    def sample_tools(self) -> List[McpToolWrapper]:
        """创建示例工具的测试夹具"""
        return create_sample_mcp_tools()

    def test_create_sample_mcp_tools(self, sample_tools: List[McpToolWrapper]) -> None:
        """测试 MCP 工具创建功能"""
        # 验证工具数量
        assert len(sample_tools) == 3, f"期望 3 个工具，实际得到 {len(sample_tools)} 个"

        # 验证工具名称
        tool_names = [tool_wrapper["tool"].name for tool_wrapper in sample_tools]
        expected_names = ["get_current_time", "calculator", "text_processor"]
        assert all(
            name in tool_names for name in expected_names
        ), f"工具名称不匹配: {tool_names}"

        # 验证工具结构
        for tool_wrapper in sample_tools:
            assert "tool" in tool_wrapper, "工具包装器缺少 tool 字段"
            assert "function" in tool_wrapper, "工具包装器缺少 function 字段"

            tool = tool_wrapper["tool"]
            assert hasattr(tool, "name"), "MCP工具缺少 name 属性"
            assert hasattr(tool, "description"), "MCP工具缺少 description 属性"
            assert hasattr(tool, "inputSchema"), "MCP工具缺少 inputSchema 属性"
            assert callable(
                tool_wrapper["function"]
            ), "工具的 function 字段必须是可调用的"

    def test_get_current_time_tool(self, sample_tools: List[McpToolWrapper]) -> None:
        """测试时间查询工具"""
        result = execute_mcp_tool("get_current_time", {}, sample_tools)

        # 验证返回格式（应该是 YYYY-MM-DD HH:MM:SS 格式）
        assert isinstance(result, str), "时间工具应该返回字符串"
        assert len(result) == 19, f"时间格式应该是 19 个字符，实际: {len(result)}"

        # 验证时间格式的基本结构
        parts = result.split(" ")
        assert len(parts) == 2, "时间应该包含日期和时间两部分"

        date_part, time_part = parts
        assert len(date_part.split("-")) == 3, "日期部分应该有年月日三部分"
        assert len(time_part.split(":")) == 3, "时间部分应该有时分秒三部分"

    def test_calculator_tool_basic_operations(
        self, sample_tools: List[McpToolWrapper]
    ) -> None:
        """测试计算器工具的基本运算"""
        test_cases = [
            ("2+3", "计算结果：5"),
            ("10-4", "计算结果：6"),
            ("3*4", "计算结果：12"),
            ("15/3", "计算结果：5.0"),
            ("2+3*4", "计算结果：14"),
            ("(2+3)*4", "计算结果：20"),
        ]

        for expression, expected in test_cases:
            result = execute_mcp_tool(
                "calculator", {"expression": expression}, sample_tools
            )
            assert (
                result == expected
            ), f"表达式 {expression} 计算错误: 期望 {expected}, 实际 {result}"

    def test_calculator_tool_error_handling(
        self, sample_tools: List[McpToolWrapper]
    ) -> None:
        """测试计算器工具的错误处理"""
        # 测试非法字符
        result = execute_mcp_tool(
            "calculator", {"expression": "2+3+import"}, sample_tools
        )
        assert "错误" in result, "应该检测到非法字符"

        # 测试除零错误
        result = execute_mcp_tool("calculator", {"expression": "1/0"}, sample_tools)
        assert "计算错误" in result, "应该检测到除零错误"

        # 测试语法错误
        result = execute_mcp_tool("calculator", {"expression": "2++"}, sample_tools)
        assert "计算错误" in result, "应该检测到语法错误"

    def test_text_processor_tool_operations(
        self, sample_tools: List[McpToolWrapper]
    ) -> None:
        """测试文本处理工具的各种操作"""
        test_text = "Hello World"

        test_cases = [
            ("upper", "HELLO WORLD"),
            ("lower", "hello world"),
            ("reverse", "dlroW olleH"),
            ("count", "字符数：11"),
        ]

        for operation, expected in test_cases:
            result = execute_mcp_tool(
                "text_processor",
                {"text": test_text, "operation": operation},
                sample_tools,
            )
            assert (
                result == expected
            ), f"文本操作 {operation} 错误: 期望 {expected}, 实际 {result}"

    def test_text_processor_tool_invalid_operation(
        self, sample_tools: List[McpToolWrapper]
    ) -> None:
        """测试文本处理工具的无效操作处理"""
        result = execute_mcp_tool(
            "text_processor", {"text": "test", "operation": "invalid_op"}, sample_tools
        )
        assert "不支持的操作" in result, "应该检测到不支持的操作"

    def test_execute_mcp_tool_nonexistent_tool(
        self, sample_tools: List[McpToolWrapper]
    ) -> None:
        """测试执行不存在的工具"""
        result = execute_mcp_tool("nonexistent_tool", {}, sample_tools)
        assert "未找到" in result, "应该返回工具未找到的错误信息"

    def test_execute_mcp_tool_error_handling(
        self, sample_tools: List[McpToolWrapper]
    ) -> None:
        """测试工具执行的错误处理"""
        # 测试缺少必要参数
        result = execute_mcp_tool("calculator", {}, sample_tools)
        assert "工具执行失败" in result or "错误" in result, "应该处理缺少参数的情况"


class TestMcpState:
    """MCP 状态管理测试类"""

    def test_mcp_state_creation(self) -> None:
        """测试 MCP 状态创建"""
        tools = create_sample_mcp_tools()

        state: McpState = {
            "messages": [],
            "tools_available": tools,
            "tool_outputs": [],
            "enable_tools": True,
        }

        # 验证状态结构
        assert "messages" in state, "状态应该包含 messages 字段"
        assert "tools_available" in state, "状态应该包含 tools_available 字段"
        assert "tool_outputs" in state, "状态应该包含 tool_outputs 字段"
        assert "enable_tools" in state, "状态应该包含 enable_tools 字段"

        # 验证状态值
        assert isinstance(state["messages"], list), "messages 应该是列表"
        assert isinstance(state["tools_available"], list), "tools_available 应该是列表"
        assert isinstance(state["tool_outputs"], list), "tool_outputs 应该是列表"
        assert isinstance(state["enable_tools"], bool), "enable_tools 应该是布尔值"

        # 验证工具数量
        assert (
            len(state["tools_available"]) == 3
        ), f"应该有 3 个可用工具，实际: {len(state['tools_available'])}"

    def test_mcp_state_disabled_tools(self) -> None:
        """测试禁用工具的 MCP 状态"""
        state: McpState = {
            "messages": [],
            "tools_available": [],
            "tool_outputs": [],
            "enable_tools": False,
        }

        assert state["enable_tools"] is False, "工具应该被禁用"
        assert len(state["tools_available"]) == 0, "禁用工具时应该没有可用工具"


class TestMcpIntegration:
    """MCP 集成测试类"""

    def test_full_mcp_workflow(self) -> None:
        """测试完整的 MCP 工作流程"""
        # 1. 创建工具
        tools = create_sample_mcp_tools()
        assert len(tools) > 0, "应该能创建工具"

        # 2. 创建状态
        state: McpState = {
            "messages": [],
            "tools_available": tools,
            "tool_outputs": [],
            "enable_tools": True,
        }

        # 3. 执行工具并记录结果
        time_result = execute_mcp_tool("get_current_time", {}, tools)
        calc_result = execute_mcp_tool("calculator", {"expression": "5*5"}, tools)

        # 4. 更新状态
        state["tool_outputs"].extend(
            [
                {"tool": "get_current_time", "result": time_result},
                {"tool": "calculator", "result": calc_result},
            ]
        )

        # 5. 验证最终状态
        assert len(state["tool_outputs"]) == 2, "应该有两个工具执行记录"
        assert "计算结果：25" in calc_result, "计算器应该正确计算 5*5=25"
        assert len(time_result) == 19, "时间格式应该正确"


if __name__ == "__main__":
    # 支持直接运行测试
    pytest.main([__file__, "-v"])
