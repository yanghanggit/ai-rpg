from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import traceback
from typing import Annotated, Any, Dict, List

from langchain.schema import AIMessage
from langchain_core.messages import BaseMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr
from typing_extensions import TypedDict

# MCP imports
from mcp.types import Tool


# 简化的 MCP 工具包装器，包含 MCP Tool 和执行函数
class McpToolWrapper(TypedDict):
    tool: Tool  # 真正的 MCP Tool 对象
    function: Any  # 实际执行函数


############################################################################################################
class McpState(TypedDict):
    """
    MCP 增强的状态，包含消息和工具相关信息
    """

    messages: Annotated[List[BaseMessage], add_messages]
    tools_available: List[McpToolWrapper]  # 可用的 MCP 工具
    tool_outputs: List[Dict[str, Any]]  # 工具执行结果
    enable_tools: bool  # 是否启用工具调用


############################################################################################################
def create_sample_mcp_tools() -> List[McpToolWrapper]:
    """
    创建示例 MCP 工具，使用真正的 MCP Tool 对象

    Returns:
        List[McpToolWrapper]: MCP 工具包装器列表
    """
    tools: List[McpToolWrapper] = []

    # 示例工具1：获取当前时间
    def get_current_time() -> str:
        """获取当前时间"""
        import datetime

        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 示例工具2：简单计算器
    def calculator(expression: str) -> str:
        """
        安全的计算器工具

        Args:
            expression: 数学表达式，如 "2+3*4"

        Returns:
            str: 计算结果
        """
        try:
            # 安全的数学表达式求值（仅允许数字和基本运算符）
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in expression):
                return "错误：表达式包含不允许的字符"

            result = eval(expression)
            return f"计算结果：{result}"
        except Exception as e:
            return f"计算错误：{str(e)}"

    # 示例工具3：文本处理
    def text_processor(text: str, operation: str = "upper") -> str:
        """
        文本处理工具

        Args:
            text: 要处理的文本
            operation: 操作类型 (upper/lower/reverse/count)

        Returns:
            str: 处理结果
        """
        try:
            if operation == "upper":
                return text.upper()
            elif operation == "lower":
                return text.lower()
            elif operation == "reverse":
                return text[::-1]
            elif operation == "count":
                return f"字符数：{len(text)}"
            else:
                return f"不支持的操作：{operation}"
        except Exception as e:
            return f"处理错误：{str(e)}"

    # 创建真正的 MCP Tool 对象
    time_tool = Tool(
        name="get_current_time",
        description="获取当前系统时间",
        inputSchema={"type": "object", "properties": {}, "required": []},
    )

    calculator_tool = Tool(
        name="calculator",
        description="执行数学计算",
        inputSchema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，如 '2+3*4'",
                }
            },
            "required": ["expression"],
        },
    )

    text_processor_tool = Tool(
        name="text_processor",
        description="处理文本内容",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要处理的文本"},
                "operation": {
                    "type": "string",
                    "description": "操作类型：upper/lower/reverse/count",
                    "default": "upper",
                },
            },
            "required": ["text"],
        },
    )

    # 创建工具包装器
    tools_data: List[McpToolWrapper] = [
        {
            "tool": time_tool,
            "function": get_current_time,
        },
        {
            "tool": calculator_tool,
            "function": calculator,
        },
        {
            "tool": text_processor_tool,
            "function": text_processor,
        },
    ]

    tools.extend(tools_data)

    return tools


############################################################################################################
def execute_mcp_tool(
    tool_name: str, tool_args: Dict[str, Any], available_tools: List[McpToolWrapper]
) -> str:
    """
    执行 MCP 工具

    Args:
        tool_name: 工具名称
        tool_args: 工具参数
        available_tools: 可用工具包装器列表

    Returns:
        str: 工具执行结果
    """
    try:
        # 查找对应的工具
        target_tool_wrapper = None
        for tool_wrapper in available_tools:
            if tool_wrapper["tool"].name == tool_name:
                target_tool_wrapper = tool_wrapper
                break

        if not target_tool_wrapper:
            return f"工具 '{tool_name}' 未找到"

        # 执行工具函数
        tool_function = target_tool_wrapper["function"]
        result = tool_function(**tool_args)

        logger.info(f"MCP工具执行: {tool_name} | 参数: {tool_args} | 结果: {result}")
        return str(result)

    except Exception as e:
        error_msg = f"工具执行失败: {tool_name} | 错误: {str(e)}"
        logger.error(error_msg)
        return error_msg


############################################################################################################
def create_compiled_mcp_stage_graph(
    node_name: str, temperature: float, enable_tools: bool = True
) -> CompiledStateGraph[McpState, Any, McpState, McpState]:
    """
    创建带 MCP 支持的编译状态图

    Args:
        node_name: 节点名称
        temperature: 模型温度
        enable_tools: 是否启用工具调用

    Returns:
        CompiledStateGraph: 编译后的状态图
    """
    assert node_name != "", "node_name is empty"

    # 检查必需的环境变量
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

    # 初始化 DeepSeek LLM
    llm = ChatDeepSeek(
        api_key=SecretStr(deepseek_api_key),
        model="deepseek-chat",
        temperature=temperature,
    )

    # 初始化 MCP 工具
    available_tools = create_sample_mcp_tools() if enable_tools else []

    def invoke_deepseek_mcp_action(state: McpState) -> Dict[str, Any]:
        """
        DeepSeek + MCP 动作节点

        Args:
            state: 当前状态

        Returns:
            Dict: 更新后的状态
        """
        try:
            messages = state["messages"]
            tools_available = state.get("tools_available", available_tools)
            enable_tools_flag = state.get("enable_tools", enable_tools)

            # 构建系统提示，包含工具信息
            system_prompt = """你是一个智能助手，具有使用工具的能力。

当你需要获取实时信息或执行特定操作时，可以调用相应的工具。请按照以下格式调用工具：

<tool_call>
<tool_name>工具名称</tool_name>
<tool_args>{"参数名": "参数值"}</tool_args>
</tool_call>

你可以在回复中自然地解释你要做什么，然后调用工具，最后根据工具结果给出完整回答。"""

            if enable_tools_flag and tools_available:
                tool_descriptions = []
                for tool_wrapper in tools_available:
                    tool = tool_wrapper["tool"]
                    params_desc = ""

                    # 从 MCP Tool 的 inputSchema 中提取参数描述
                    if tool.inputSchema and "properties" in tool.inputSchema:
                        param_list = []
                        properties = tool.inputSchema["properties"]
                        required = tool.inputSchema.get("required", [])

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
                or not isinstance(enhanced_messages[0], type(messages[0]))
                or "你是一个智能助手" not in str(enhanced_messages[0].content)
            ):
                from langchain.schema import SystemMessage

                enhanced_messages.insert(0, SystemMessage(content=system_prompt))

            # 调用 LLM
            response = llm.invoke(enhanced_messages)

            # 解析响应，检查是否包含工具调用
            tool_outputs = []
            if enable_tools_flag and tools_available:
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
                            tool_wrapper["tool"].name == tool_name
                            for tool_wrapper in tools_available
                        )
                        if not tool_exists:
                            logger.warning(f"工具 {tool_name} 不存在")
                            continue

                        # 执行工具
                        tool_result = execute_mcp_tool(
                            tool_name, tool_args, tools_available
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
                "tools_available": tools_available,
                "tool_outputs": tool_outputs,
                "enable_tools": enable_tools_flag,
            }

        except Exception as e:
            logger.error(f"Error in MCP action: {e}\n{traceback.format_exc()}")
            error_message = AIMessage(content=f"抱歉，处理请求时发生错误：{str(e)}")
            return {
                "messages": [error_message],
                "tools_available": available_tools,
                "tool_outputs": [],
                "enable_tools": enable_tools,
            }

    # 构建状态图
    graph_builder = StateGraph(McpState)
    graph_builder.add_node(node_name, invoke_deepseek_mcp_action)
    graph_builder.set_entry_point(node_name)
    graph_builder.set_finish_point(node_name)

    return graph_builder.compile()  # type: ignore[return-value]


############################################################################################################
def stream_mcp_graph_updates(
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
        "tools_available": user_input_state.get(
            "tools_available", chat_history_state.get("tools_available", [])
        ),
        "tool_outputs": chat_history_state.get("tool_outputs", []),
        "enable_tools": user_input_state.get(
            "enable_tools", chat_history_state.get("enable_tools", True)
        ),
    }

    try:
        for event in state_compiled_graph.stream(merged_message_context):
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
