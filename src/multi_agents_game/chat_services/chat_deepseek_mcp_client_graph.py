from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import traceback
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
from ..config import McpConfig, load_mcp_config

# 全局 ChatDeepSeek 实例
_global_deepseek_llm: Optional[ChatDeepSeek] = None

_mcp_config: Optional[McpConfig] = None


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
        # logger.info(f"ChatDeepSeek 实例已创建，温度: {temperature}")

    return _global_deepseek_llm


############################################################################################################
def _get_mcp_config() -> McpConfig:
    global _mcp_config
    if _mcp_config is None:
        _mcp_config = load_mcp_config(Path("mcp_config.json"))
        assert _mcp_config is not None, "MCP config loading failed"
    return _mcp_config


############################################################################################################
class McpState(TypedDict):
    """
    MCP 增强的状态，包含消息和 MCP 客户端相关信息
    """

    messages: Annotated[List[BaseMessage], add_messages]
    mcp_client: Optional[McpClient]  # MCP 客户端
    available_tools: List[McpToolInfo]  # 可用的 MCP 工具
    tool_outputs: List[Dict[str, Any]]  # 工具执行结果


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
async def create_compiled_mcp_stage_graph(
    node_name: str,
    mcp_client: McpClient,
) -> CompiledStateGraph[McpState, Any, McpState, McpState]:
    """
    创建带 MCP 支持的编译状态图

    Args:
        node_name: 节点名称
        temperature: 模型温度
        mcp_server_url: MCP 服务器地址

    Returns:
        CompiledStateGraph: 编译后的状态图
    """
    assert node_name != "", "node_name is empty"

    # 获取 ChatDeepSeek 实例（懒加载）
    llm = get_deepseek_llm()
    assert llm is not None, "ChatDeepSeek instance is not available"

    # mcp_config = _get_mcp_config()

    # 初始化 MCP 客户端
    # mcp_client = None
    available_tools = []

    try:
        # mcp_client = await initialize_mcp_client(
        #     mcp_server_url=mcp_config.mcp_server_url,
        #     mcp_protocol_version=mcp_config.protocol_version,
        #     mcp_timeout=mcp_config.mcp_timeout,
        # )
        available_tools = await mcp_client.get_available_tools()
        logger.info(f"MCP 工具初始化完成，可用工具数量: {len(available_tools)}")
    except Exception as e:
        logger.error(f"MCP 客户端初始化失败: {e}")
        # MCP 初始化失败，但继续运行（只是没有工具支持）

    async def invoke_deepseek_mcp_action(state: McpState) -> Dict[str, Any]:
        """
        DeepSeek + MCP 动作节点

        Args:
            state: 当前状态

        Returns:
            Dict: 更新后的状态
        """
        try:
            messages = state["messages"]
            current_mcp_client = state.get("mcp_client", mcp_client)
            current_available_tools = state.get("available_tools", available_tools)

            # 构建系统提示，包含工具信息
            system_prompt = """你是一个智能助手，具有使用工具的能力。

当你需要获取实时信息或执行特定操作时，可以调用相应的工具。请按照以下格式调用工具：

<tool_call>
<tool_name>工具名称</tool_name>
<tool_args>{"参数名": "参数值"}</tool_args>
</tool_call>

你可以在回复中自然地解释你要做什么，然后调用工具，最后根据工具结果给出完整回答。"""

            if current_available_tools and current_mcp_client:
                tool_descriptions = []
                for tool in current_available_tools:
                    params_desc = ""

                    # 从工具的 input_schema 中提取参数描述
                    if tool.input_schema and "properties" in tool.input_schema:
                        param_list = []
                        properties = tool.input_schema["properties"]
                        required = tool.input_schema.get("required", [])

                        for param_name, param_info in properties.items():
                            param_desc = param_info.get("description", "无描述")
                            is_required = (
                                " (必需)" if param_name in required else " (可选)"
                            )
                            param_list.append(
                                f"{param_name}: {param_desc}{is_required}"
                            )

                        params_desc = (
                            f" 参数: {', '.join(param_list)}" if param_list else ""
                        )

                    tool_desc = f"- {tool.name}: {tool.description}{params_desc}"
                    tool_descriptions.append(tool_desc)

                system_prompt += f"\n\n可用工具：\n{chr(10).join(tool_descriptions)}"

            # 添加系统消息到对话开头（如果还没有）
            enhanced_messages = messages.copy()
            if (
                not enhanced_messages
                or not isinstance(enhanced_messages[0], SystemMessage)
                or "你是一个智能助手" not in str(enhanced_messages[0].content)
            ):
                enhanced_messages.insert(0, SystemMessage(content=system_prompt))

            # 调用 LLM
            response = llm.invoke(enhanced_messages)

            # 解析响应，检查是否包含工具调用
            tool_outputs = []
            if current_available_tools and current_mcp_client:
                # 解析 LLM 响应中的工具调用请求
                response_content = str(response.content) if response.content else ""

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
                            tool.name == tool_name for tool in current_available_tools
                        )
                        if not tool_exists:
                            logger.warning(f"工具 {tool_name} 不存在")
                            continue

                        # 执行工具
                        tool_result = await execute_mcp_tool(
                            tool_name, tool_args, current_mcp_client
                        )
                        tool_outputs.append(
                            {
                                "tool": tool_name,
                                "args": tool_args,
                                "result": tool_result,
                            }
                        )

                        logger.info(f"工具调用成功: {tool_name} -> {tool_result}")

                    except json.JSONDecodeError as e:
                        logger.error(f"工具参数解析失败: {tool_args_str}, 错误: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"工具执行异常: {tool_name}, 错误: {e}")
                        continue

                # 如果有工具被执行，更新响应内容
                if tool_outputs:
                    # 移除原始的工具调用标记，添加工具执行结果
                    updated_content = re.sub(
                        tool_call_pattern, "", response_content, flags=re.DOTALL
                    )

                    # 添加工具执行结果
                    for tool_output in tool_outputs:
                        updated_content += f"\n\n🔧 {tool_output['tool']} 执行结果：\n{tool_output['result']}"

                    response.content = updated_content.strip()

            return {
                "messages": [response],
                "mcp_client": current_mcp_client,
                "available_tools": current_available_tools,
                "tool_outputs": tool_outputs,
            }

        except Exception as e:
            logger.error(f"Error in MCP action: {e}\n{traceback.format_exc()}")
            error_message = AIMessage(content=f"抱歉，处理请求时发生错误：{str(e)}")
            return {
                "messages": [error_message],
                "mcp_client": mcp_client,
                "available_tools": available_tools,
                "tool_outputs": [],
            }

    # 构建状态图
    graph_builder = StateGraph(McpState)
    graph_builder.add_node(node_name, invoke_deepseek_mcp_action)
    graph_builder.set_entry_point(node_name)
    graph_builder.set_finish_point(node_name)

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
                ret.extend(value["messages"])
                # 记录工具执行信息
                if value.get("tool_outputs"):
                    logger.info(f"工具执行记录: {value['tool_outputs']}")
    except Exception as e:
        logger.error(f"Stream processing error: {e}")
        error_message = AIMessage(content="抱歉，处理消息时发生错误。")
        ret.append(error_message)

    return ret
