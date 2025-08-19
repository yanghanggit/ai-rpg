"""
统一 MCP 客户端实现 - Streamable HTTP 传输

基于 MCP 2025-06-18 规范的 Streamable HTTP 传输实现。
支持标准的 HTTP POST/GET 请求和 Server-Sent Events (SSE) 流。
"""

import os
import json
import uuid
import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from loguru import logger
from pydantic import BaseModel

# MCP SDK 导入
import mcp.types as types


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
    """统一 MCP 客户端实现 - 使用 Streamable HTTP 传输"""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8765",
        protocol_version: str = "2024-11-05",
        timeout: int = 30,
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
                }
            )

            # 执行 MCP 初始化
            await self._initialize_mcp()
            
            logger.success(f"✅ MCP 客户端已连接 (transport: streamable-http, session: {self.session_id[:8] if self.session_id else 'no-session'}...)")

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
                "capabilities": {
                    "experimental": {},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "MCP Python Client",
                    "version": "1.0.0"
                }
            }
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
        notification_data = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        await self._post_notification("/mcp", notification_data)
        self._initialized = True

    async def _post_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
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
            if response.status >= 400:
                text = await response.text()
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"HTTP {response.status}: {text}"
                )
            
            # 检查响应内容类型
            content_type = response.headers.get("Content-Type", "")
            logger.debug(f"📋 响应内容类型: {content_type}")
            logger.debug(f"📋 响应头: {dict(response.headers)}")
            
            if "application/json" in content_type:
                result = await response.json()
                
                # 检查并提取会话 ID（使用正确的头部名称）
                if not self.session_id:
                    session_headers = ["mcp-session-id", "Mcp-Session-Id", "MCP-Session-Id"]
                    for header in session_headers:
                        if header in response.headers:
                            self.session_id = response.headers[header]
                            logger.info(f"🔗 从响应头 {header} 提取会话ID: {self.session_id[:8]}...")
                            break
                    
                    # 也尝试从响应体中提取会话ID
                    if not self.session_id and isinstance(result, dict):
                        if "sessionId" in result:
                            self.session_id = result["sessionId"]
                            logger.info(f"🔗 从响应体提取会话ID: {self.session_id[:8]}...")
                    
                return result
            elif "text/event-stream" in content_type:
                # SSE响应也需要提取会话ID
                if not self.session_id:
                    session_headers = ["mcp-session-id", "Mcp-Session-Id", "MCP-Session-Id"]
                    for header in session_headers:
                        if header in response.headers:
                            self.session_id = response.headers[header]
                            logger.info(f"🔗 从SSE响应头 {header} 提取会话ID: {self.session_id[:8]}...")
                            break
                
                # 处理 SSE 流
                return await self._handle_sse_stream(response)
                # 处理 SSE 流
                return await self._handle_sse_stream(response)
            else:
                raise RuntimeError(f"不支持的响应类型: {content_type}")

    async def _post_notification(self, endpoint: str, data: Dict[str, Any]) -> None:
        """发送 POST 通知到 MCP 服务器"""
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
            # 通知应该返回 202 Accepted
            if response.status != 202:
                text = await response.text()
                raise RuntimeError(f"通知失败 HTTP {response.status}: {text}")

    async def _handle_sse_stream(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """处理 Server-Sent Events 流"""
        result = None
        
        async for line in response.content:
            line = line.decode('utf-8').strip()
            
            if line.startswith('data: '):
                data_str = line[6:]  # 移除 'data: ' 前缀
                try:
                    data = json.loads(data_str)
                    
                    # 检查是否是我们期待的响应
                    if data.get("jsonrpc") == "2.0" and ("result" in data or "error" in data):
                        result = data
                        break
                        
                except json.JSONDecodeError:
                    continue
        
        if result is None:
            raise RuntimeError("未收到有效的 JSON-RPC 响应")
            
        return result

    async def disconnect(self) -> None:
        """断开与 MCP 服务器的连接"""
        try:
            # 发送会话终止请求（如果支持）
            if self.session_id and self.http_session:
                try:
                    headers = {"Mcp-Session-Id": self.session_id}
                    async with self.http_session.delete(self.base_url, headers=headers) as response:
                        pass  # 忽略响应（服务器可能不支持 DELETE）
                except:
                    pass  # 忽略错误

            # 关闭 HTTP 会话
            if self.http_session:
                await self.http_session.close()
                self.http_session = None

            self.session_id = None
            self._initialized = False
            
            logger.info("🔌 MCP 客户端已断开连接")

        except Exception as e:
            logger.error(f"❌ 断开 MCP 连接时出错: {e}")

    async def check_health(self) -> bool:
        """检查连接健康状态"""
        try:
            if not self.http_session or not self._initialized:
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
            if not self.http_session or not self._initialized:
                raise RuntimeError("MCP 客户端未连接")

            # 构建 list_tools 请求
            request_data = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/list",
                "params": {}
            }

            # 发送请求
            response = await self._post_request("/mcp", request_data)
            
            # 检查错误
            if "error" in response:
                raise RuntimeError(f"获取工具列表失败: {response['error']}")

            # 解析工具列表
            tools = []
            result = response.get("result", {})
            tool_list = result.get("tools", [])
            
            for tool in tool_list:
                tools.append(
                    McpToolInfo(
                        name=tool.get("name", ""),
                        description=tool.get("description", ""),
                        input_schema=tool.get("inputSchema", {}),
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
            if not self.http_session or not self._initialized:
                raise RuntimeError("MCP 客户端未连接")

            # 构建 call_tool 请求
            request_data = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            # 发送请求
            response = await self._post_request("/mcp", request_data)
            
            execution_time = time.time() - start_time

            # 检查错误
            if "error" in response:
                error_info = response["error"]
                error_msg = f"{error_info.get('code', 'UNKNOWN')}: {error_info.get('message', '未知错误')}"
                
                logger.error(f"❌ 工具调用失败: {tool_name} | {error_msg}")
                
                return McpToolResult(
                    success=False,
                    result=None,
                    error=error_msg,
                    execution_time=execution_time,
                )

            # 提取结果内容
            result = response.get("result", {})
            content_list = result.get("content", [])
            
            result_content = []
            for content in content_list:
                if content.get("type") == "text":
                    result_content.append(content.get("text", ""))
                else:
                    result_content.append(str(content))

            result_text = "\n".join(result_content) if result_content else "工具执行完成"

            logger.info(f"🔧 工具调用成功: {tool_name} -> {result_text[:100]}...")

            return McpToolResult(
                success=True, 
                result=result_text, 
                execution_time=execution_time
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
            if not self.http_session or not self._initialized:
                raise RuntimeError("MCP 客户端未连接")

            # 构建 list_resources 请求
            request_data = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "resources/list",
                "params": {}
            }

            response = await self._post_request("/mcp", request_data)
            
            if "error" in response:
                raise RuntimeError(f"获取资源列表失败: {response['error']}")

            result = response.get("result", {})
            resources = result.get("resources", [])
            
            return [resource.get("uri", "") for resource in resources]

        except Exception as e:
            logger.error(f"❌ 获取资源列表失败: {e}")
            return []

    async def read_resource(self, uri: str) -> Optional[str]:
        """读取资源内容"""
        try:
            if not self.http_session or not self._initialized:
                raise RuntimeError("MCP 客户端未连接")

            # 构建 read_resource 请求
            request_data = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "resources/read",
                "params": {
                    "uri": uri
                }
            }

            response = await self._post_request("/mcp", request_data)
            
            if "error" in response:
                raise RuntimeError(f"读取资源失败: {response['error']}")

            # 提取资源内容
            result = response.get("result", {})
            contents = result.get("contents", [])
            
            content_texts = []
            for content in contents:
                if content.get("type") == "text":
                    content_texts.append(content.get("text", ""))
                else:
                    content_texts.append(str(content))

            return "\n".join(content_texts) if content_texts else None

        except Exception as e:
            logger.error(f"❌ 读取资源失败: {uri} | {e}")
            return None

    async def list_prompts(self) -> List[str]:
        """列出可用提示模板"""
        try:
            if not self.http_session or not self._initialized:
                raise RuntimeError("MCP 客户端未连接")

            # 构建 list_prompts 请求
            request_data = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "prompts/list",
                "params": {}
            }

            response = await self._post_request("/mcp", request_data)
            
            if "error" in response:
                raise RuntimeError(f"获取提示列表失败: {response['error']}")

            result = response.get("result", {})
            prompts = result.get("prompts", [])
            
            return [prompt.get("name", "") for prompt in prompts]

        except Exception as e:
            logger.error(f"❌ 获取提示列表失败: {e}")
            return []

    async def get_prompt(
        self, name: str, arguments: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """获取提示模板内容"""
        try:
            if not self.http_session or not self._initialized:
                raise RuntimeError("MCP 客户端未连接")

            # 构建 get_prompt 请求
            request_data = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "prompts/get",
                "params": {
                    "name": name,
                    "arguments": arguments or {}
                }
            }

            response = await self._post_request("/mcp", request_data)
            
            if "error" in response:
                raise RuntimeError(f"获取提示模板失败: {response['error']}")

            # 提取提示内容
            result = response.get("result", {})
            messages = result.get("messages", [])
            
            message_texts = []
            for message in messages:
                content = message.get("content", {})
                if content.get("type") == "text":
                    message_texts.append(content.get("text", ""))

            return "\n".join(message_texts) if message_texts else None

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
    base_url: str = "http://127.0.0.1:8765",
    protocol_version: str = "2024-11-05",
    timeout: int = 30,
) -> McpClient:
    """创建 MCP 客户端（Streamable HTTP 模式）"""
    return McpClient(
        base_url=base_url,
        protocol_version=protocol_version,
        timeout=timeout
    )
