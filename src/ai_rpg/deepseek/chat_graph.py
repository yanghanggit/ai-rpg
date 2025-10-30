from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import traceback
from typing import Annotated, Any, List
from langchain_core.messages import BaseMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict


############################################################################################################
class ChatState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    llm: ChatDeepSeek


############################################################################################################
def _chatbot_node(
    state: ChatState,
) -> ChatState:
    """聊天机器人节点，最简单的实现"""
    try:

        llm = state["llm"]  # 使用状态中的LLM实例
        assert llm is not None, "LLM instance is None in state"
        return {"messages": [llm.invoke(state["messages"])], "llm": llm}

    except Exception as e:

        logger.error(f"Error invoking DeepSeek LLM: {e}\n" f"State: {state}")
        traceback.print_exc()

        return {
            "messages": [],
            "llm": state["llm"],
        }  # 当出现内容过滤的情况，或者其他类型异常时，视需求可在此返回空字符串或者自定义提示。


############################################################################################################
def create_chat_workflow() -> CompiledStateGraph[ChatState, Any, ChatState, ChatState]:
    """创建并编译 DeepSeek 聊天图"""

    graph_builder = StateGraph(ChatState)
    graph_builder.add_node("chatbot_node", _chatbot_node)
    graph_builder.set_entry_point("chatbot_node")
    graph_builder.set_finish_point("chatbot_node")
    return graph_builder.compile()  # type: ignore[return-value]


############################################################################################################
async def execute_chat_workflow(
    work_flow: CompiledStateGraph[ChatState, Any, ChatState, ChatState],
    context: ChatState,
    request: ChatState,
) -> List[BaseMessage]:
    """执行聊天工作流并返回所有响应消息

    将聊天历史和用户输入合并后，通过编译好的状态图进行流式处理，
    收集并返回所有生成的消息。

    Args:
        state_compiled_graph: 已编译的 LangGraph 状态图
        chat_history_state: 包含历史消息的聊天状态
        user_input_state: 包含用户当前输入的聊天状态

    Returns:
        包含所有生成消息的列表
    """
    ret: List[BaseMessage] = []

    merged_message_context: ChatState = {
        "messages": context["messages"] + request["messages"],
        "llm": context["llm"],  # 使用聊天历史状态中的LLM实例
    }

    async for event in work_flow.astream(merged_message_context):
        for value in event.values():
            ret.extend(value["messages"])

    return ret


############################################################################################################
