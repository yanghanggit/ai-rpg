from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
from typing import Annotated, Any, Dict, List, Optional

from langchain.schema import AIMessage, SystemMessage
from langchain_core.messages import BaseMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr
from typing_extensions import TypedDict

# 导入统一 MCP 客户端
from .mcp_client import McpClient, McpToolInfo

# 全局 ChatDeepSeek 实例
_global_deepseek_llm: Optional[ChatDeepSeek] = None


############################################################################################################
def get_deepseek_llm() -> ChatDeepSeek:
    """
    获取 ChatDeepSeek 实例（懒加载）

    Args:
        temperature: 模型温度，默认为 0.7

    Returns:
        ChatDeepSeek: ChatDeepSeek 实例

    Raises:
        ValueError: 如果 DEEPSEEK_API_KEY 环境变量未设置
    """
    global _global_deepseek_llm

    if _global_deepseek_llm is None:
        # 检查必需的环境变量
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

        # 创建 ChatDeepSeek 实例
        _global_deepseek_llm = ChatDeepSeek(
            api_key=SecretStr(deepseek_api_key),
            model="deepseek-chat",
            temperature=0.7,
        )

    return _global_deepseek_llm


############################################################################################################
class McpState(TypedDict, total=False):
    """
    MCP 增强的状态，包含消息和 MCP 客户端相关信息
    """

    messages: Annotated[List[BaseMessage], add_messages]
    mcp_client: Optional[McpClient]  # MCP 客户端
    available_tools: List[McpToolInfo]  # 可用的 MCP 工具
    tool_outputs: List[Dict[str, Any]]  # 工具执行结果

    # 新增字段用于多节点流程
    system_prompt: Optional[str]  # 系统提示缓存
    enhanced_messages: List[BaseMessage]  # 包含系统提示的增强消息
    llm_response: Optional[BaseMessage]  # LLM原始响应
    parsed_tool_calls: List[Dict[str, Any]]  # 解析出的工具调用
    needs_tool_execution: bool  # 是否需要执行工具


############################################################################################################
async def initialize_mcp_client(
    mcp_server_url: str, mcp_protocol_version: str, mcp_timeout: int
) -> McpClient:
    """
    初始化 MCP 客户端

    Args:
        server_url: MCP 服务器地址（Streamable HTTP 模式）

    Returns:
        McpClient: 初始化后的 MCP 客户端
    """
    # 使用 Streamable HTTP 模式（标准 2025-06-18 规范）
    client = McpClient(
        base_url=mcp_server_url,
        protocol_version=mcp_protocol_version,
        timeout=mcp_timeout,
    )

    # 连接到服务器
    await client.connect()

    # 检查服务器健康状态
    if not await client.check_health():
        await client.disconnect()
        raise ConnectionError(f"无法连接到 MCP 服务器: {mcp_server_url}")

    logger.info(f"MCP 客户端初始化成功: {mcp_server_url}")
    return client


############################################################################################################
async def execute_mcp_tool(
    tool_name: str, tool_args: Dict[str, Any], mcp_client: McpClient
) -> str:
    """
    通过 MCP 客户端执行工具

    Args:
        tool_name: 工具名称
        tool_args: 工具参数
        mcp_client: MCP 客户端

    Returns:
        str: 工具执行结果
    """
    try:
        result = await mcp_client.call_tool(tool_name, tool_args)

        if result.success:
            logger.info(
                f"MCP工具执行成功: {tool_name} | 参数: {tool_args} | 结果: {result.result}"
            )
            return str(result.result)
        else:
            error_msg = f"工具执行失败: {tool_name} | 错误: {result.error}"
            logger.error(error_msg)
            return error_msg

    except Exception as e:
        error_msg = f"工具执行异常: {tool_name} | 错误: {str(e)}"
        logger.error(error_msg)
        return error_msg


############################################################################################################
async def _build_system_prompt(available_tools: List[McpToolInfo]) -> str:
    """
    构建系统提示，包含工具信息

    Args:
        available_tools: 可用工具列表

    Returns:
        str: 构建好的系统提示
    """
    system_prompt = """你是一个智能助手，具有使用工具的能力。

当你需要获取实时信息或执行特定操作时，可以调用相应的工具。请按照以下格式调用工具：

<tool_call>
<tool_name>工具名称</tool_name>
<tool_args>{"参数名": "参数值"}</tool_args>
</tool_call>

你可以在回复中自然地解释你要做什么，然后调用工具，最后根据工具结果给出完整回答。"""

    if available_tools:
        tool_descriptions = []
        for tool in available_tools:
            params_desc = ""

            # 从工具的 input_schema 中提取参数描述
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

        system_prompt += f"\n\n可用工具：\n{chr(10).join(tool_descriptions)}"

    return system_prompt


############################################################################################################
async def _preprocess_node(state: McpState) -> McpState:
    """
    预处理节点：准备系统提示和增强消息

    Args:
        state: 当前状态

    Returns:
        McpState: 更新后的状态
    """
    try:
        messages = state["messages"]
        available_tools = state.get("available_tools", [])

        # 构建系统提示
        system_prompt = await _build_system_prompt(available_tools)

        # 添加系统消息到对话开头（如果还没有）
        enhanced_messages = messages.copy()
        if (
            not enhanced_messages
            or not isinstance(enhanced_messages[0], SystemMessage)
            or "你是一个智能助手" not in str(enhanced_messages[0].content)
        ):
            enhanced_messages.insert(0, SystemMessage(content=system_prompt))

        result: McpState = {
            "messages": [],  # 预处理节点不返回消息，避免重复累积
            "mcp_client": state.get("mcp_client"),
            "available_tools": available_tools,
            "tool_outputs": state.get("tool_outputs", []),
            "system_prompt": system_prompt,  # 保存系统提示供后续使用
            "enhanced_messages": enhanced_messages,  # 保存增强消息供LLM使用
        }
        return result

    except Exception as e:
        logger.error(f"预处理节点错误: {e}")
        return state


############################################################################################################
async def _llm_invoke_node(state: McpState) -> McpState:
    """
    LLM调用节点：调用DeepSeek生成响应

    Args:
        state: 当前状态

    Returns:
        McpState: 更新后的状态
    """
    try:
        # 获取 ChatDeepSeek 实例
        llm = get_deepseek_llm()

        # 使用增强消息（包含系统提示）进行LLM调用
        enhanced_messages = state.get("enhanced_messages", state["messages"])

        # 调用 LLM
        response = llm.invoke(enhanced_messages)

        result: McpState = {
            "messages": [],  # LLM调用节点不返回消息，避免重复累积
            "mcp_client": state.get("mcp_client"),
            "available_tools": state.get("available_tools", []),
            "tool_outputs": state.get("tool_outputs", []),
            "llm_response": response,  # 保存LLM响应供后续处理
            "enhanced_messages": enhanced_messages,  # 传递增强消息
        }
        return result

    except Exception as e:
        logger.error(f"LLM调用节点错误: {e}")
        error_message = AIMessage(content=f"抱歉，处理请求时发生错误：{str(e)}")
        llm_error_result: McpState = {
            "messages": [error_message],  # 只返回错误消息
            "mcp_client": state.get("mcp_client"),
            "available_tools": state.get("available_tools", []),
            "tool_outputs": [],
        }
        return llm_error_result


############################################################################################################
async def _tool_parse_node(state: McpState) -> McpState:
    """
    工具解析节点：解析LLM响应中的工具调用

    Args:
        state: 当前状态

    Returns:
        McpState: 更新后的状态
    """
    try:
        llm_response = state.get("llm_response")
        available_tools = state.get("available_tools", [])

        parsed_tool_calls = []

        if llm_response and available_tools:
            response_content = str(llm_response.content) if llm_response.content else ""

            # 使用正则表达式提取工具调用
            import re
            import json

            tool_call_pattern = r"<tool_call>\s*<tool_name>(.*?)</tool_name>\s*<tool_args>(.*?)</tool_args>\s*</tool_call>"
            tool_calls = re.findall(tool_call_pattern, response_content, re.DOTALL)

            for tool_name, tool_args_str in tool_calls:
                tool_name = tool_name.strip()
                tool_args_str = tool_args_str.strip()

                try:
                    # 解析工具参数
                    if tool_args_str:
                        tool_args = json.loads(tool_args_str)
                    else:
                        tool_args = {}

                    # 验证工具是否存在
                    tool_exists = any(
                        tool.name == tool_name for tool in available_tools
                    )
                    if not tool_exists:
                        logger.warning(f"工具 {tool_name} 不存在")
                        continue

                    parsed_tool_calls.append(
                        {
                            "name": tool_name,
                            "args": tool_args,
                        }
                    )

                except json.JSONDecodeError as e:
                    logger.error(f"工具参数解析失败: {tool_args_str}, 错误: {e}")
                    continue

        result: McpState = {
            "messages": [],  # 工具解析节点不返回消息，避免重复累积
            "mcp_client": state.get("mcp_client"),
            "available_tools": available_tools,
            "tool_outputs": state.get("tool_outputs", []),
            "llm_response": llm_response,
            "parsed_tool_calls": parsed_tool_calls,
            "needs_tool_execution": len(parsed_tool_calls) > 0,
        }
        return result

    except Exception as e:
        logger.error(f"工具解析节点错误: {e}")
        return state


############################################################################################################
async def _tool_execution_node(state: McpState) -> McpState:
    """
    工具执行节点：执行解析出的工具调用

    Args:
        state: 当前状态

    Returns:
        McpState: 更新后的状态
    """
    try:
        parsed_tool_calls = state.get("parsed_tool_calls", [])
        mcp_client = state.get("mcp_client")

        tool_outputs = []

        if parsed_tool_calls and mcp_client:
            for tool_call in parsed_tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                try:
                    # 执行工具
                    tool_result = await execute_mcp_tool(
                        tool_name, tool_args, mcp_client
                    )
                    tool_outputs.append(
                        {
                            "tool": tool_name,
                            "args": tool_args,
                            "result": tool_result,
                        }
                    )

                    logger.info(f"工具调用成功: {tool_name} -> {tool_result}")

                except Exception as e:
                    logger.error(f"工具执行异常: {tool_name}, 错误: {e}")
                    continue

        result: McpState = {
            "messages": [],  # 工具执行节点不返回消息，避免重复累积
            "mcp_client": mcp_client,
            "available_tools": state.get("available_tools", []),
            "tool_outputs": tool_outputs,
            "llm_response": state.get("llm_response"),
            "parsed_tool_calls": parsed_tool_calls,
        }
        return result

    except Exception as e:
        logger.error(f"工具执行节点错误: {e}")
        return state


############################################################################################################
async def _response_synthesis_node(state: McpState) -> McpState:
    """
    响应合成节点：将工具结果整合到最终响应

    Args:
        state: 当前状态

    Returns:
        McpState: 更新后的状态
    """
    try:
        llm_response = state.get("llm_response")
        tool_outputs = state.get("tool_outputs", [])
        parsed_tool_calls = state.get("parsed_tool_calls", [])

        if not llm_response:
            error_message = AIMessage(content="抱歉，没有收到LLM响应。")
            synthesis_error_result: McpState = {
                "messages": [error_message],
                "mcp_client": state.get("mcp_client"),
                "available_tools": state.get("available_tools", []),
                "tool_outputs": tool_outputs,
            }
            return synthesis_error_result

        # 如果有工具被执行，更新响应内容
        if tool_outputs:
            import re

            response_content = str(llm_response.content) if llm_response.content else ""
            tool_call_pattern = r"<tool_call>\s*<tool_name>.*?</tool_name>\s*<tool_args>.*?</tool_args>\s*</tool_call>"

            # 移除原始的工具调用标记
            updated_content = re.sub(
                tool_call_pattern, "", response_content, flags=re.DOTALL
            )

            # 添加工具执行结果
            for tool_output in tool_outputs:
                updated_content += (
                    f"\n\n🔧 {tool_output['tool']} 执行结果：\n{tool_output['result']}"
                )

            llm_response.content = updated_content.strip()

        result: McpState = {
            "messages": [llm_response],
            "mcp_client": state.get("mcp_client"),
            "available_tools": state.get("available_tools", []),
            "tool_outputs": tool_outputs,
        }
        return result

    except Exception as e:
        logger.error(f"响应合成节点错误: {e}")
        error_message = AIMessage(content=f"抱歉，合成响应时发生错误：{str(e)}")
        synthesis_exception_result: McpState = {
            "messages": [error_message],
            "mcp_client": state.get("mcp_client"),
            "available_tools": state.get("available_tools", []),
            "tool_outputs": [],
        }
        return synthesis_exception_result


############################################################################################################
def _should_execute_tools(state: McpState) -> str:
    """
    条件路由：判断是否需要执行工具

    Args:
        state: 当前状态

    Returns:
        str: 下一个节点名称
    """
    needs_tool_execution = state.get("needs_tool_execution", False)
    return "tool_execution" if needs_tool_execution else "response_synthesis"


############################################################################################################
async def create_compiled_mcp_stage_graph(
    node_name: str,
    mcp_client: McpClient,
) -> CompiledStateGraph[McpState, Any, McpState, McpState]:
    """
    创建带 MCP 支持的编译状态图（多节点架构）

    Args:
        node_name: 基础节点名称前缀
        mcp_client: MCP客户端实例

    Returns:
        CompiledStateGraph: 编译后的状态图
    """
    assert node_name != "", "node_name is empty"
    assert mcp_client is not None, "mcp_client is required"

    # 获取 ChatDeepSeek 实例（懒加载）
    llm = get_deepseek_llm()
    assert llm is not None, "ChatDeepSeek instance is not available"

    # 初始化 MCP 工具
    available_tools = []
    try:
        available_tools = await mcp_client.get_available_tools()
        logger.info(f"MCP 工具初始化完成，可用工具数量: {len(available_tools)}")
    except Exception as e:
        logger.error(f"MCP 客户端初始化失败: {e}")
        # MCP 初始化失败，但继续运行（只是没有工具支持）

    # 创建包装函数，传递必要的上下文
    async def preprocess_wrapper(state: McpState) -> McpState:
        # 确保状态包含必要信息
        state_with_context: McpState = {
            "messages": state.get("messages", []),
            "mcp_client": state.get("mcp_client", mcp_client),
            "available_tools": state.get("available_tools", available_tools),
            "tool_outputs": state.get("tool_outputs", []),
        }
        return await _preprocess_node(state_with_context)

    async def error_fallback_wrapper(state: McpState) -> McpState:
        """错误处理包装器，确保总能返回有效响应"""
        try:
            # 如果之前的节点都失败了，提供一个基本的错误响应
            if not state.get("messages"):
                error_message = AIMessage(content="抱歉，处理请求时发生错误。")
                fallback_result: McpState = {
                    "messages": [error_message],
                    "mcp_client": mcp_client,
                    "available_tools": available_tools,
                    "tool_outputs": [],
                }
                return fallback_result
            return state
        except Exception as e:
            logger.error(f"错误处理包装器失败: {e}")
            error_message = AIMessage(content="抱歉，系统发生未知错误。")
            fallback_exception_result: McpState = {
                "messages": [error_message],
                "mcp_client": mcp_client,
                "available_tools": available_tools,
                "tool_outputs": [],
            }
            return fallback_exception_result

    # 构建多节点状态图
    graph_builder = StateGraph(McpState)

    # 添加各个节点
    graph_builder.add_node("preprocess", preprocess_wrapper)
    graph_builder.add_node("llm_invoke", _llm_invoke_node)
    graph_builder.add_node("tool_parse", _tool_parse_node)
    graph_builder.add_node("tool_execution", _tool_execution_node)
    graph_builder.add_node("response_synthesis", _response_synthesis_node)
    graph_builder.add_node("error_fallback", error_fallback_wrapper)

    # 设置流程路径
    graph_builder.set_entry_point("preprocess")
    graph_builder.add_edge("preprocess", "llm_invoke")
    graph_builder.add_edge("llm_invoke", "tool_parse")

    # 添加条件路由
    graph_builder.add_conditional_edges(
        "tool_parse",
        _should_execute_tools,
        {
            "tool_execution": "tool_execution",
            "response_synthesis": "response_synthesis",
        },
    )

    graph_builder.add_edge("tool_execution", "response_synthesis")
    graph_builder.set_finish_point("response_synthesis")

    return graph_builder.compile()  # type: ignore[return-value]


############################################################################################################
async def stream_mcp_graph_updates(
    state_compiled_graph: CompiledStateGraph[McpState, Any, McpState, McpState],
    chat_history_state: McpState,
    user_input_state: McpState,
) -> List[BaseMessage]:
    """
    流式处理 MCP 图更新

    Args:
        state_compiled_graph: 编译后的状态图
        chat_history_state: 聊天历史状态
        user_input_state: 用户输入状态

    Returns:
        List[BaseMessage]: 响应消息列表
    """
    ret: List[BaseMessage] = []

    # 合并状态，保持 MCP 相关信息
    merged_message_context: McpState = {
        "messages": chat_history_state["messages"] + user_input_state["messages"],
        "mcp_client": user_input_state.get(
            "mcp_client", chat_history_state.get("mcp_client")
        ),
        "available_tools": user_input_state.get(
            "available_tools", chat_history_state.get("available_tools", [])
        ),
        "tool_outputs": chat_history_state.get("tool_outputs", []),
    }

    try:
        async for event in state_compiled_graph.astream(merged_message_context):
            for value in event.values():
                # 只收集非空的消息（主要是最终的AI回复）
                if value.get("messages"):
                    ret.extend(value["messages"])
                # 记录工具执行信息
                if value.get("tool_outputs"):
                    logger.info(f"工具执行记录: {value['tool_outputs']}")
    except Exception as e:
        logger.error(f"Stream processing error: {e}")
        error_message = AIMessage(content="抱歉，处理消息时发生错误。")
        ret.append(error_message)

    return ret
