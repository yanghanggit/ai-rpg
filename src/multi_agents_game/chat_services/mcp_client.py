"""
统一 MCP 客户端实现

基于官方 MCP Python SDK 的标准客户端实现，使用 stdio 传输协议。
专注于稳定性和可靠性，遵循官方推荐的 stdio 传输方式。
"""

import os
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel

# MCP SDK 导入
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class McpToolInfo(BaseModel):
    """MCP 工具信息"""

    name: str
    description: str
    input_schema: Dict[str, Any]


class McpToolResult(BaseModel):
    """MCP 工具执行结果"""

    success: bool
    result: Any
    error: Optional[str] = None
    execution_time: float


class McpClient:
    """统一 MCP 客户端实现 - 使用 stdio 传输"""

    def __init__(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        """
        初始化 MCP 客户端

        Args:
            command: 服务器命令（如 "python"）
            args: 服务器参数（如 ["scripts/run_sample_mcp_server.py"]）
            env: 环境变量
        """
        # 设置默认配置
        self.command = command or "python"
        self.args = args or ["scripts/run_sample_mcp_server.py"]
        self.env = env or {}

        # 内部状态
        self.session: Optional[ClientSession] = None
        self._tools_cache: Optional[List[McpToolInfo]] = None
        self._connection_context: Optional[Any] = None

    async def __aenter__(self) -> "McpClient":
        """异步上下文管理器入口"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口"""
        await self.disconnect()

    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        try:
            await self._connect_stdio()
            logger.success("✅ MCP 客户端已连接 (transport: stdio)")

        except Exception as e:
            logger.error(f"❌ MCP 客户端连接失败: {e}")
            raise

    async def _connect_stdio(self) -> None:
        """连接 stdio 模式的服务器"""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env={**os.environ, **self.env} if self.env else None,
        )

        # 使用 stdio_client 连接
        self._connection_context = stdio_client(server_params)
        read_stream, write_stream = await self._connection_context.__aenter__()

        # 创建会话
        self.session = ClientSession(read_stream, write_stream)
        await self.session.initialize()

    async def disconnect(self) -> None:
        """断开与 MCP 服务器的连接"""
        try:
            if self.session:
                # 注意：ClientSession 没有 close 方法，连接会在上下文管理器退出时自动关闭
                self.session = None

            if self._connection_context:
                await self._connection_context.__aexit__(None, None, None)
                self._connection_context = None

            logger.info("🔌 MCP 客户端已断开连接")

        except Exception as e:
            logger.error(f"❌ 断开 MCP 连接时出错: {e}")

    async def check_health(self) -> bool:
        """检查连接健康状态"""
        try:
            if not self.session:
                return False

            # 尝试列出工具来检查连接
            await self.get_available_tools()
            return True

        except Exception as e:
            logger.warning(f"⚠️ MCP 健康检查失败: {e}")
            return False

    async def get_available_tools(
        self, force_refresh: bool = False
    ) -> List[McpToolInfo]:
        """获取可用工具列表"""
        if not force_refresh and self._tools_cache:
            return self._tools_cache

        try:
            if not self.session:
                raise RuntimeError("MCP 客户端未连接")

            # 调用标准 MCP 协议
            response = await self.session.list_tools()

            tools = []
            for tool in response.tools:
                tools.append(
                    McpToolInfo(
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema or {},
                    )
                )

            self._tools_cache = tools
            logger.info(f"📋 获取到 {len(tools)} 个可用工具")
            return tools

        except Exception as e:
            logger.error(f"❌ 获取工具列表失败: {e}")
            return []

    async def get_tool_info(self, tool_name: str) -> Optional[McpToolInfo]:
        """获取指定工具信息"""
        try:
            tools = await self.get_available_tools()
            for tool in tools:
                if tool.name == tool_name:
                    return tool
            return None

        except Exception as e:
            logger.error(f"❌ 获取工具信息失败: {tool_name} | {e}")
            return None

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> McpToolResult:
        """调用工具"""
        import time

        start_time = time.time()

        try:
            if not self.session:
                raise RuntimeError("MCP 客户端未连接")

            # 调用标准 MCP 协议
            response = await self.session.call_tool(tool_name, arguments)

            execution_time = time.time() - start_time

            # 提取结果内容
            result_content = []
            for content in response.content:
                if content.type == "text":
                    result_content.append(content.text)
                else:
                    result_content.append(str(content))

            result = "\n".join(result_content) if result_content else "工具执行完成"

            logger.info(f"🔧 工具调用成功: {tool_name} -> {result[:100]}...")

            return McpToolResult(
                success=True, result=result, execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)

            logger.error(f"❌ 工具调用失败: {tool_name} | {error_msg}")

            return McpToolResult(
                success=False,
                result=None,
                error=error_msg,
                execution_time=execution_time,
            )

    async def call_tool_simple(self, tool_name: str, **kwargs: Any) -> Any:
        """简化的工具调用方法，直接返回结果"""
        result = await self.call_tool(tool_name, kwargs)
        if result.success:
            return result.result
        else:
            raise Exception(result.error or "工具调用失败")

    async def list_resources(self) -> List[str]:
        """列出可用资源"""
        try:
            if not self.session:
                raise RuntimeError("MCP 客户端未连接")

            response = await self.session.list_resources()
            return [str(resource.uri) for resource in response.resources]

        except Exception as e:
            logger.error(f"❌ 获取资源列表失败: {e}")
            return []

    async def read_resource(self, uri: str) -> Optional[str]:
        """读取资源内容"""
        try:
            if not self.session:
                raise RuntimeError("MCP 客户端未连接")

            response = await self.session.read_resource(uri)  # type: ignore[arg-type]

            # 提取资源内容
            contents = []
            for content in response.contents:
                if hasattr(content, "type") and getattr(content, "type") == "text":
                    contents.append(getattr(content, "text", str(content)))
                else:
                    contents.append(str(content))

            return "\n".join(contents) if contents else None

        except Exception as e:
            logger.error(f"❌ 读取资源失败: {uri} | {e}")
            return None

    async def list_prompts(self) -> List[str]:
        """列出可用提示模板"""
        try:
            if not self.session:
                raise RuntimeError("MCP 客户端未连接")

            response = await self.session.list_prompts()
            return [prompt.name for prompt in response.prompts]

        except Exception as e:
            logger.error(f"❌ 获取提示列表失败: {e}")
            return []

    async def get_prompt(
        self, name: str, arguments: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """获取提示模板内容"""
        try:
            if not self.session:
                raise RuntimeError("MCP 客户端未连接")

            response = await self.session.get_prompt(name, arguments or {})

            # 提取提示内容
            messages = []
            for message in response.messages:
                if hasattr(message, "content") and hasattr(message.content, "text"):
                    messages.append(message.content.text)

            return "\n".join(messages) if messages else None

        except Exception as e:
            logger.error(f"❌ 获取提示模板失败: {name} | {e}")
            return None

    def format_tools_for_prompt(self, tools: Optional[List[McpToolInfo]] = None) -> str:
        """格式化工具信息用于提示词"""
        if tools is None:
            return "获取工具列表失败"

        if not tools:
            return "当前没有可用工具"

        tool_descriptions = []
        for tool in tools:
            params_desc = ""

            if tool.input_schema and "properties" in tool.input_schema:
                param_list = []
                properties = tool.input_schema["properties"]
                required = tool.input_schema.get("required", [])

                for param_name, param_info in properties.items():
                    param_desc = param_info.get("description", "无描述")
                    is_required = " (必需)" if param_name in required else " (可选)"
                    param_list.append(f"{param_name}: {param_desc}{is_required}")

                params_desc = f" 参数: {', '.join(param_list)}" if param_list else ""

            tool_desc = f"- {tool.name}: {tool.description}{params_desc}"
            tool_descriptions.append(tool_desc)

        return "\n".join(tool_descriptions)


# ============================================================================
# 工厂函数
# ============================================================================


def create_mcp_client(
    command: Optional[str] = None,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
) -> McpClient:
    """创建 MCP 客户端（stdio 模式）"""
    return McpClient(command=command, args=args, env=env)
