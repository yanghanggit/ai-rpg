from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import asyncio
from typing import Annotated, Any, Dict, List, Optional

from langchain.schema import AIMessage, SystemMessage
from langchain_core.messages import BaseMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr
from typing_extensions import TypedDict

# 导入统一 MCP 客户端和功能
from ..mcp import (
    McpClient,
    McpToolInfo,
    ToolCallParser,
    execute_mcp_tool,
    build_json_tool_example,
    format_tool_description_simple,
    synthesize_response_with_tools,
)

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
def _build_system_prompt(available_tools: List[McpToolInfo]) -> str:
    """
    构建系统提示，仅支持JSON格式工具调用

    Args:
        available_tools: 可用工具列表

    Returns:
        str: 构建好的系统提示
    """
    # 工具使用说明（不包含角色设定）
    system_prompt = """当你需要获取实时信息或执行特定操作时，可以调用相应的工具。

## 工具调用格式

请严格按照以下JSON格式调用工具：

```json
{
  "tool_call": {
    "name": "工具名称",
    "arguments": {
      "参数名": "参数值"
    }
  }
}
```

## 使用指南

- 你可以在回复中自然地解释你要做什么
- 然后在回复中包含JSON格式的工具调用
- 工具执行完成后，根据结果给出完整的回答
- 如果工具执行失败，请为用户提供替代方案或解释原因"""

    if not available_tools:
        system_prompt += "\n\n⚠️ 当前没有可用工具，请仅使用你的知识回答问题。"
        return system_prompt

    # 构建工具描述 - 简化版本，统一使用线性展示
    system_prompt += "\n\n## 可用工具"

    # 直接列表展示所有工具，无需分类
    for tool in available_tools:
        tool_desc = format_tool_description_simple(tool)
        system_prompt += f"\n{tool_desc}"

    # 添加实际工具的调用示例
    example_tool = available_tools[0]
    system_prompt += f"\n\n## 调用示例\n\n"
    system_prompt += build_json_tool_example(example_tool)

    return system_prompt


# def _format_tool_description(tool: McpToolInfo) -> str:
#     """格式化单个工具的描述"""
#     try:
#         params_desc = ""

#         # 从工具的 input_schema 中提取参数描述
#         if tool.input_schema and "properties" in tool.input_schema:
#             param_list = []
#             properties = tool.input_schema["properties"]
#             required = tool.input_schema.get("required", [])

#             for param_name, param_info in properties.items():
#                 param_desc = param_info.get("description", "无描述")
#                 param_type = param_info.get("type", "string")
#                 is_required = "**必需**" if param_name in required else "*可选*"

#                 param_list.append(
#                     f"  - `{param_name}` ({param_type}): {param_desc} [{is_required}]"
#                 )

#             if param_list:
#                 params_desc = f"\n{chr(10).join(param_list)}"

#         tool_desc = f"- **{tool.name}**: {tool.description}"
#         if params_desc:
#             tool_desc += f"\n  参数:{params_desc}"

#         return tool_desc

#     except Exception as e:
#         logger.warning(f"格式化工具描述失败: {tool.name}, 错误: {e}")
#         return f"- **{tool.name}**: {tool.description}"


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
        system_prompt = _build_system_prompt(available_tools)

        # 智能添加系统消息：如果已有系统消息则追加，否则插入到开头
        enhanced_messages = messages.copy()
        if enhanced_messages and isinstance(enhanced_messages[0], SystemMessage):
            # 已经有系统消息在开头，追加新的工具说明
            enhanced_messages.append(SystemMessage(content=system_prompt))
        else:
            # 没有系统消息，插入默认角色设定和工具说明到开头
            default_role_prompt = (
                "你是一个智能助手，具有使用工具的能力。\n\n" + system_prompt
            )
            enhanced_messages.insert(0, SystemMessage(content=default_role_prompt))

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
    工具解析节点：使用增强解析器解析LLM响应中的工具调用

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

            # 使用增强的工具调用解析器
            parser = ToolCallParser(available_tools)
            parsed_tool_calls = parser.parse_tool_calls(response_content)

            logger.info(f"📋 解析到 {len(parsed_tool_calls)} 个工具调用")
            for call in parsed_tool_calls:
                logger.debug(f"   - {call['name']}: {call['args']}")

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
        # 发生错误时，继续流程但不执行工具
        error_result: McpState = {
            "messages": [],
            "mcp_client": state.get("mcp_client"),
            "available_tools": state.get("available_tools", []),
            "tool_outputs": state.get("tool_outputs", []),
            "llm_response": state.get("llm_response"),
            "parsed_tool_calls": [],
            "needs_tool_execution": False,
        }
        return error_result


############################################################################################################
async def _tool_execution_node(state: McpState) -> McpState:
    """
    工具执行节点：执行解析出的工具调用（增强版）

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
            logger.info(f"🔧 开始执行 {len(parsed_tool_calls)} 个工具调用")

            # 使用 asyncio.gather() 统一处理所有工具调用（真正并发执行）
            tasks = []
            for tool_call in parsed_tool_calls:
                task = execute_mcp_tool(
                    tool_call["name"],
                    tool_call["args"],
                    mcp_client,
                    timeout=30.0,
                    max_retries=2,  # 统一使用2次重试
                )
                tasks.append((tool_call, task))

            # 真正并发执行所有任务
            try:
                execution_results = await asyncio.gather(
                    *[task for _, task in tasks], return_exceptions=True
                )

                for (tool_call, _), exec_result in zip(tasks, execution_results):
                    if isinstance(exec_result, Exception):
                        logger.error(
                            f"工具执行任务失败: {tool_call['name']}, 错误: {exec_result}"
                        )
                        tool_outputs.append(
                            {
                                "tool": tool_call["name"],
                                "args": tool_call["args"],
                                "result": f"执行失败: {str(exec_result)}",
                                "success": False,
                                "execution_time": 0.0,
                            }
                        )
                    elif isinstance(exec_result, tuple) and len(exec_result) == 3:
                        success, task_result, exec_time = exec_result
                        tool_outputs.append(
                            {
                                "tool": tool_call["name"],
                                "args": tool_call["args"],
                                "result": task_result,
                                "success": success,
                                "execution_time": exec_time,
                            }
                        )
                    else:
                        # 意外的结果类型
                        logger.error(
                            f"工具执行返回意外结果类型: {tool_call['name']}, 结果: {exec_result}"
                        )
                        tool_outputs.append(
                            {
                                "tool": tool_call["name"],
                                "args": tool_call["args"],
                                "result": f"意外结果类型: {type(exec_result)}",
                                "success": False,
                                "execution_time": 0.0,
                            }
                        )
            except Exception as e:
                logger.error(f"并发执行工具失败: {e}")
                # 降级处理：为所有工具调用记录错误
                for tool_call in parsed_tool_calls:
                    tool_outputs.append(
                        {
                            "tool": tool_call["name"],
                            "args": tool_call["args"],
                            "result": f"并发执行失败: {str(e)}",
                            "success": False,
                            "execution_time": 0.0,
                        }
                    )

            # 统计执行结果
            successful_calls = sum(1 for output in tool_outputs if output["success"])
            total_time = sum(output["execution_time"] for output in tool_outputs)

            logger.info(
                f"✅ 工具执行完成: {successful_calls}/{len(tool_outputs)} 成功, "
                f"总耗时: {total_time:.2f}s"
            )

        final_result: McpState = {
            "messages": [],  # 工具执行节点不返回消息，避免重复累积
            "mcp_client": mcp_client,
            "available_tools": state.get("available_tools", []),
            "tool_outputs": tool_outputs,
            "llm_response": state.get("llm_response"),
            "parsed_tool_calls": parsed_tool_calls,
        }
        return final_result

    except Exception as e:
        logger.error(f"工具执行节点错误: {e}")
        # 即使执行失败，也要返回状态以继续流程
        error_result: McpState = {
            "messages": [],
            "mcp_client": state.get("mcp_client"),
            "available_tools": state.get("available_tools", []),
            "tool_outputs": [
                {
                    "tool": "系统",
                    "args": {},
                    "result": f"工具执行节点发生错误: {str(e)}",
                    "success": False,
                    "execution_time": 0.0,
                }
            ],
            "llm_response": state.get("llm_response"),
            "parsed_tool_calls": state.get("parsed_tool_calls", []),
        }
        return error_result


############################################################################################################
async def _response_synthesis_node(state: McpState) -> McpState:
    """
    响应合成节点：智能地将工具结果整合到最终响应（增强版）

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

        response_content = str(llm_response.content) if llm_response.content else ""

        # 如果有工具被执行，智能合成响应
        if tool_outputs:
            synthesized_content = synthesize_response_with_tools(
                response_content, tool_outputs, parsed_tool_calls
            )
            llm_response.content = synthesized_content

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
        tools_result = await mcp_client.list_tools()
        available_tools = tools_result if tools_result is not None else []
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
