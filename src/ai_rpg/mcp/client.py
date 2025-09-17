"""
统一 MCP 客户端实现 - Streamable HTTP 传输

基于 MCP 2025-06-18 规范的 Streamable HTTP 传输实现。
支持标准的 HTTP POST/GET 请求和 Server-Sent Events (SSE) 流。
"""

import json
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from loguru import logger

from .models import McpToolInfo, McpToolResult


class McpClient:
    """统一 MCP 客户端实现 - 使用 Streamable HTTP 传输"""

    def __init__(
        self,
        base_url: str,
        protocol_version: str,
        timeout: int,
    ):
        """
        初始化 MCP 客户端

        Args:
            base_url: MCP 服务器基础 URL
            protocol_version: MCP 协议版本
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.protocol_version = protocol_version
        self.timeout = timeout

        # 内部状态
        self.session_id: Optional[str] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self._tools_cache: Optional[List[McpToolInfo]] = None
        self._initialized = False

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
            # 创建 HTTP 会话
            self.http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": self.protocol_version,
                },
            )

            # 执行 MCP 初始化
            await self._initialize_mcp()

            logger.success(
                f"✅ MCP 客户端已连接 (transport: streamable-http, session: {self.session_id[:8] if self.session_id else 'no-session'}...)"
            )

        except Exception as e:
            logger.error(f"❌ MCP 客户端连接失败: {e}")
            if self.http_session:
                await self.http_session.close()
            raise

    async def _initialize_mcp(self) -> None:
        """执行 MCP 初始化协议"""
        # 构建 InitializeRequest
        request_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": self.protocol_version,
                "capabilities": {"experimental": {}, "sampling": {}},
                "clientInfo": {"name": "MCP Python Client", "version": "1.0.0"},
            },
        }

        # 发送初始化请求
        response = await self._post_request("/mcp", request_data)

        # 检查响应
        if "error" in response:
            raise RuntimeError(f"初始化失败: {response['error']}")

        # 确保会话ID已获取
        if not self.session_id:
            raise RuntimeError("服务器未返回会话ID")

        logger.info(f"🔗 MCP 会话已建立，会话ID: {self.session_id[:8]}...")

        # 发送 initialized 通知
        notification_data = {"jsonrpc": "2.0", "method": "notifications/initialized"}

        await self._post_notification("/mcp", notification_data)
        self._initialized = True

    async def _post_request(
        self, endpoint: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """发送 POST 请求到 MCP 服务器"""
        if not self.http_session:
            raise RuntimeError("HTTP 会话未初始化")

        url = urljoin(self.base_url, endpoint)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol_version,
        }

        # 添加会话 ID（如果有）
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        async with self.http_session.post(url, json=data, headers=headers) as response:
            # 检查会话ID
            session_id = response.headers.get("mcp-session-id")
            if session_id and not self.session_id:
                self.session_id = session_id
                logger.debug(f"🆔 获取到会话ID: {session_id[:8]}...")

            if response.status == 404:
                raise RuntimeError(f"MCP 服务器端点未找到: {url}")

            if response.status >= 400:
                error_text = await response.text()
                raise RuntimeError(f"MCP 服务器错误 {response.status}: {error_text}")

            content_type = response.headers.get("content-type", "")

            if "text/event-stream" in content_type:
                # 处理 SSE 流
                return await self._handle_sse_response(response)
            else:
                # 处理普通 JSON 响应
                json_result = await response.json()
                if isinstance(json_result, dict):
                    return json_result
                else:
                    return {"data": json_result}

    async def _post_notification(self, endpoint: str, data: Dict[str, Any]) -> None:
        """发送通知到 MCP 服务器（不期望响应）"""
        if not self.http_session:
            raise RuntimeError("HTTP 会话未初始化")

        url = urljoin(self.base_url, endpoint)
        headers = {
            "Content-Type": "application/json",
            "MCP-Protocol-Version": self.protocol_version,
        }

        # 添加会话 ID（如果有）
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        async with self.http_session.post(url, json=data, headers=headers) as response:
            if response.status >= 400:
                error_text = await response.text()
                logger.warning(f"通知发送失败 {response.status}: {error_text}")

    async def _handle_sse_response(
        self, response: aiohttp.ClientResponse
    ) -> Dict[str, Any]:
        """处理 Server-Sent Events 响应"""
        final_result: Dict[str, Any] = {}

        async for line in response.content:
            line_str = line.decode("utf-8").strip()

            if line_str.startswith("data: "):
                data_str = line_str[6:]  # 移除 "data: " 前缀

                try:
                    data = json.loads(data_str)
                    if isinstance(data, dict):
                        final_result = data
                    else:
                        final_result = {"data": data}
                except json.JSONDecodeError:
                    logger.warning(f"无法解析 SSE 数据: {data_str}")

        return final_result

    async def disconnect(self) -> None:
        """断开 MCP 连接"""
        if self.http_session:
            await self.http_session.close()
            self.http_session = None

        self.session_id = None
        self._tools_cache = None
        self._initialized = False
        logger.info("🔌 MCP 客户端已断开连接")

    async def check_health(self) -> bool:
        """检查 MCP 服务器健康状态"""
        try:
            if not self.http_session:
                return False

            # 发送健康检查请求
            health_request = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "ping",
            }

            response = await self._post_request("/health", health_request)

            # 检查响应
            return "error" not in response

        except Exception as e:
            logger.warning(f"健康检查失败: {e}")
            return False

    async def list_tools(self) -> Optional[List[McpToolInfo]]:
        """获取可用工具列表"""
        try:
            # 检查缓存
            if self._tools_cache is not None:
                return self._tools_cache

            # 构建工具列表请求
            tools_request = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/list",
            }

            response = await self._post_request("/mcp", tools_request)

            # 检查响应
            if "error" in response:
                logger.error(f"获取工具列表失败: {response['error']}")
                return None

            # 解析工具信息
            tools_data = response.get("result", {}).get("tools", [])
            tools = []

            for tool_data in tools_data:
                try:
                    tool = McpToolInfo(
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        input_schema=tool_data.get("inputSchema", {}),
                    )
                    tools.append(tool)
                except Exception as e:
                    logger.warning(f"解析工具信息失败: {e}, 数据: {tool_data}")

            # 缓存结果
            self._tools_cache = tools
            logger.info(f"✅ 获取到 {len(tools)} 个工具")

            return tools

        except Exception as e:
            logger.error(f"获取工具列表时发生错误: {e}")
            return None

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> McpToolResult:
        """调用 MCP 工具"""
        import time

        start_time = time.time()

        try:
            # 构建工具调用请求
            call_request = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }

            response = await self._post_request("/mcp", call_request)
            execution_time = time.time() - start_time

            # 检查响应
            if "error" in response:
                error_msg = response["error"].get("message", "未知错误")
                logger.error(f"工具调用失败: {error_msg}")
                return McpToolResult(
                    success=False,
                    result=None,
                    error=error_msg,
                    execution_time=execution_time,
                )

            # 提取结果
            result = response.get("result", {})
            content = result.get("content", [])

            # 处理结果内容
            if content:
                # 提取文本内容
                text_results = []
                for item in content:
                    if item.get("type") == "text":
                        text_results.append(item.get("text", ""))

                final_result = "\n".join(text_results) if text_results else str(content)
            else:
                final_result = result

            logger.success(f"✅ 工具 '{tool_name}' 调用成功")

            return McpToolResult(
                success=True,
                result=final_result,
                error=None,
                execution_time=execution_time,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"工具调用异常: {str(e)}"
            logger.error(error_msg)

            return McpToolResult(
                success=False,
                result=None,
                error=error_msg,
                execution_time=execution_time,
            )

    def format_tools_description(self) -> str:
        """格式化工具描述用于 LLM prompt"""
        import asyncio

        # 如果在异步上下文中调用，需要特殊处理
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在运行的事件循环中，返回缓存的工具或提示
                if self._tools_cache is not None:
                    tools = self._tools_cache
                else:
                    return "工具列表尚未获取，请先调用 list_tools()"
            else:
                # 没有运行的事件循环，可以创建一个
                tools_result = loop.run_until_complete(self.list_tools())
                tools = tools_result if tools_result is not None else []
        except RuntimeError:
            # 没有事件循环，创建一个临时的
            tools_result = asyncio.run(self.list_tools())
            tools = tools_result if tools_result is not None else []

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
