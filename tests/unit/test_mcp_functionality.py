"""
MCP (Model Context Protocol) 功能单元测试

测试 DeepSeek + MCP 集成的核心功能：
- MCP 客户端初始化和连接
- MCP 工具发现和调用
- MCP 状态管理
- 工具参数处理和错误处理
"""

from pathlib import Path
import pytest
from typing import Final, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch


from src.multi_agents_game.deepseek.mcp_client_graph import (
    McpState,
    initialize_mcp_client,
    execute_mcp_tool,
)
from src.multi_agents_game.mcp import (
    McpClient,
    McpToolInfo,
    McpToolResult,
)
from src.multi_agents_game.config.mcp_config import McpConfig, load_mcp_config


_mcp_config: Final[McpConfig] = load_mcp_config(Path("mcp_config.json"))


# def _get_mcp_config() -> McpConfig:
#     global _mcp_config
#     if _mcp_config is None:
#         _mcp_config = load_mcp_config(Path("mcp_config.json"))
#         assert _mcp_config is not None, "MCP config loading failed"
#     return _mcp_config


class TestMcpClient:
    """MCP 客户端功能测试类"""

    @pytest.fixture
    def mock_mcp_client(self) -> McpClient:
        """创建模拟 MCP 客户端的测试夹具"""
        client = McpClient(
            base_url=_mcp_config.mcp_server_url,
            protocol_version=_mcp_config.protocol_version,
            timeout=_mcp_config.mcp_timeout,
        )
        # Mock the http session to avoid actual network calls
        client.http_session = AsyncMock()
        client._initialized = True
        client.session_id = "test-session-123"
        return client

    @pytest.fixture
    def sample_tools(self) -> List[McpToolInfo]:
        """创建示例工具信息的测试夹具"""
        return [
            McpToolInfo(
                name="get_current_time",
                description="获取当前时间",
                input_schema={"type": "object", "properties": {}, "required": []},
            ),
            McpToolInfo(
                name="calculator",
                description="计算数学表达式",
                input_schema={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "要计算的数学表达式",
                        }
                    },
                    "required": ["expression"],
                },
            ),
            McpToolInfo(
                name="text_processor",
                description="处理文本",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "要处理的文本"},
                        "operation": {
                            "type": "string",
                            "description": "操作类型: upper, lower, reverse, count",
                        },
                    },
                    "required": ["text", "operation"],
                },
            ),
        ]

    @pytest.mark.asyncio
    async def test_mcp_client_initialization(self) -> None:
        """测试 MCP 客户端初始化"""
        # Mock the McpClient to avoid real network connections
        with patch(
            "src.multi_agents_game.deepseek.mcp_client_graph.McpClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.connect.return_value = None
            mock_client.check_health.return_value = True

            client = await initialize_mcp_client(
                _mcp_config.mcp_server_url,
                _mcp_config.protocol_version,
                _mcp_config.mcp_timeout,
            )

            # Verify that the client was created with correct parameters
            mock_client_class.assert_called_once_with(
                base_url=_mcp_config.mcp_server_url,
                protocol_version=_mcp_config.protocol_version,
                timeout=_mcp_config.mcp_timeout,
            )
            mock_client.connect.assert_called_once()
            mock_client.check_health.assert_called_once()
            assert client == mock_client

    @pytest.mark.asyncio
    async def test_mcp_client_health_check(self) -> None:
        """测试 MCP 客户端健康检查"""
        client = McpClient(
            base_url=_mcp_config.mcp_server_url,
            protocol_version=_mcp_config.protocol_version,
            timeout=_mcp_config.mcp_timeout,
        )

        # Set up the client state
        client.http_session = AsyncMock()  # Mock the http session
        client._initialized = True
        client.session_id = "test-session-123"

        # Mock the _post_request method to avoid real network calls
        with patch.object(client, "_post_request", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"result": "pong"}  # Successful ping response

            result = await client.check_health()
            assert result is True
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tools(self, sample_tools: List[McpToolInfo]) -> None:
        """测试获取可用工具"""
        client = McpClient(
            base_url=_mcp_config.mcp_server_url,
            protocol_version=_mcp_config.protocol_version,
            timeout=_mcp_config.mcp_timeout,
        )
        client.http_session = AsyncMock()
        client._initialized = True
        client.session_id = "test-session-123"

        # Mock the _post_request method to return tools list response
        mock_response = {
            "jsonrpc": "2.0",
            "id": "test-id",
            "result": {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                    for tool in sample_tools
                ]
            },
        }

        with patch.object(client, "_post_request", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            tools = await client.list_tools()

            assert tools is not None
            assert len(tools) == 3
            assert tools[0].name == "get_current_time"
            assert tools[1].name == "calculator"
            assert tools[2].name == "text_processor"

    @pytest.mark.asyncio
    async def test_call_tool_success(self) -> None:
        """测试成功调用工具"""
        client = McpClient(
            base_url=_mcp_config.mcp_server_url,
            protocol_version=_mcp_config.protocol_version,
            timeout=_mcp_config.mcp_timeout,
        )
        client.http_session = AsyncMock()
        client._initialized = True
        client.session_id = "test-session-123"

        # Mock the _post_request method to return successful tool call response
        mock_response = {
            "jsonrpc": "2.0",
            "id": "test-id",
            "result": {"content": [{"type": "text", "text": "2023-08-18 14:30:00"}]},
        }

        with patch.object(client, "_post_request", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await client.call_tool("get_current_time", {})

            assert isinstance(result, McpToolResult)
            assert result.success is True
            assert "2023-08-18 14:30:00" in result.result

    @pytest.mark.asyncio
    async def test_call_tool_failure(self) -> None:
        """测试工具调用失败"""
        client = McpClient(
            base_url=_mcp_config.mcp_server_url,
            protocol_version=_mcp_config.protocol_version,
            timeout=_mcp_config.mcp_timeout,
        )
        client.http_session = AsyncMock()
        client._initialized = True
        client.session_id = "test-session-123"

        # Mock an exception during tool call
        with patch.object(client, "_post_request", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("工具执行失败")
            result = await client.call_tool("invalid_tool", {})

            assert isinstance(result, McpToolResult)
            assert result.success is False
            assert result.error is not None and "工具执行失败" in result.error

    @pytest.mark.asyncio
    async def test_execute_mcp_tool_integration(self) -> None:
        """测试 execute_mcp_tool 函数"""
        # 创建模拟客户端
        mock_client = AsyncMock(spec=McpClient)
        mock_result = McpToolResult(
            success=True, result="计算结果：25", error=None, execution_time=0.1
        )
        mock_client.call_tool.return_value = mock_result

        result = await execute_mcp_tool(
            "calculator", {"expression": "5*5"}, mock_client
        )
        # execute_mcp_tool 现在返回 (success, result, execution_time)
        success, result_str, execution_time = result
        assert success is True, "工具执行应该成功"
        assert result_str == "计算结果：25", "应该返回正确的计算结果"
        assert execution_time >= 0, "执行时间应该非负"
        mock_client.call_tool.assert_called_once_with(
            "calculator", {"expression": "5*5"}
        )


class TestMcpState:
    """MCP 状态管理测试类"""

    def test_mcp_state_creation(self) -> None:
        """测试 MCP 状态创建"""
        # 创建模拟客户端和工具
        mock_client = MagicMock(spec=McpClient)
        sample_tools = [
            McpToolInfo(
                name="test_tool",
                description="测试工具",
                input_schema={"type": "object", "properties": {}},
            )
        ]

        state: McpState = {
            "messages": [],
            "mcp_client": mock_client,
            "available_tools": sample_tools,
            "tool_outputs": [],
        }

        # 验证状态结构
        assert "messages" in state, "状态应该包含 messages 字段"
        assert "mcp_client" in state, "状态应该包含 mcp_client 字段"
        assert "available_tools" in state, "状态应该包含 available_tools 字段"
        assert "tool_outputs" in state, "状态应该包含 tool_outputs 字段"

        # 验证状态值
        assert isinstance(state["messages"], list), "messages 应该是列表"
        assert isinstance(state["available_tools"], list), "available_tools 应该是列表"
        assert isinstance(state["tool_outputs"], list), "tool_outputs 应该是列表"

        # 验证工具数量
        assert (
            len(state["available_tools"]) == 1
        ), f"应该有 1 个可用工具，实际: {len(state['available_tools'])}"

    def test_mcp_state_no_client(self) -> None:
        """测试没有客户端的 MCP 状态"""
        state: McpState = {
            "messages": [],
            "mcp_client": None,
            "available_tools": [],
            "tool_outputs": [],
        }

        assert state["mcp_client"] is None, "没有客户端时应该为 None"
        assert len(state["available_tools"]) == 0, "没有客户端时应该没有可用工具"


class TestMcpIntegration:
    """MCP 集成测试类"""

    @pytest.mark.asyncio
    async def test_full_mcp_workflow(self) -> None:
        """测试完整的 MCP 工作流程"""
        # 1. 创建模拟客户端
        mock_client = AsyncMock(spec=McpClient)

        # 模拟工具列表
        mock_tools = [
            McpToolInfo(
                name="get_current_time",
                description="获取当前时间",
                input_schema={"type": "object", "properties": {}},
            ),
            McpToolInfo(
                name="calculator",
                description="计算器",
                input_schema={
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "数学表达式"}
                    },
                    "required": ["expression"],
                },
            ),
        ]

        mock_client.list_tools.return_value = mock_tools

        # 2. 创建状态
        state: McpState = {
            "messages": [],
            "mcp_client": mock_client,
            "available_tools": mock_tools,
            "tool_outputs": [],
        }

        # 3. 模拟工具执行结果
        time_result = McpToolResult(
            success=True, result="2023-08-18 14:30:00", error=None, execution_time=0.1
        )
        calc_result = McpToolResult(
            success=True, result="计算结果：25", error=None, execution_time=0.05
        )

        mock_client.call_tool.side_effect = [time_result, calc_result]

        # 4. 执行工具
        time_output = await execute_mcp_tool("get_current_time", {}, mock_client)
        calc_output = await execute_mcp_tool(
            "calculator", {"expression": "5*5"}, mock_client
        )

        # 5. 更新状态
        state["tool_outputs"].extend(
            [
                {"tool": "get_current_time", "result": time_output},
                {"tool": "calculator", "result": calc_output},
            ]
        )

        # 6. 验证最终状态
        assert len(state["tool_outputs"]) == 2, "应该有两个工具执行记录"
        assert "2023-08-18 14:30:00" in time_output, "时间工具应该返回正确时间"
        assert "计算结果：25" in calc_output, "计算器应该正确计算 5*5=25"

    @pytest.mark.asyncio
    async def test_mcp_error_handling(self) -> None:
        """测试 MCP 错误处理"""
        # 创建会返回错误的模拟客户端
        mock_client = AsyncMock(spec=McpClient)
        error_result = McpToolResult(
            success=False, result=None, error="工具执行失败", execution_time=0.01
        )
        mock_client.call_tool.return_value = error_result

        # 执行工具并验证错误处理
        result = await execute_mcp_tool("failing_tool", {"param": "value"}, mock_client)
        # execute_mcp_tool 现在返回 (success, result, execution_time)
        success, error_msg, execution_time = result
        assert success is False, "工具执行应该失败"
        assert "工具执行失败" in error_msg, "应该返回错误信息"
        assert execution_time >= 0, "执行时间应该非负"


if __name__ == "__main__":
    # 支持直接运行测试
    pytest.main([__file__, "-v"])
