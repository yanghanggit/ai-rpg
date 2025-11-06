from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import traceback
from typing import Annotated, Any, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict


############################################################################################################
class ChatState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    llm: AzureChatOpenAI
    llm_response: AIMessage


############################################################################################################
def _chatbot_node(
    state: ChatState,
) -> ChatState:
    """聊天机器人节点,最简单的实现"""
    llm = state["llm"]  # 使用状态中的LLM实例
    response = llm.invoke(state["messages"])  # 生成响应
    assert isinstance(response, AIMessage), "LLM 返回的响应必须是 AIMessage 类型"
    return {
        "messages": [response],  # messages 会通过 add_messages 自动合并到历史中
        "llm": llm,
        "llm_response": response,  # 单独记录最新的响应
    }


############################################################################################################
def create_chat_workflow() -> CompiledStateGraph[ChatState, Any, ChatState, ChatState]:
    """创建并编译 DeepSeek 聊天图"""

    graph_builder = StateGraph(ChatState)
    graph_builder.add_node("chatbot_node", _chatbot_node)
    graph_builder.set_entry_point("chatbot_node")
    graph_builder.set_finish_point("chatbot_node")
    return graph_builder.compile()  # type: ignore[return-value]


############################################################################################################
def print_full_message_chain(state: ChatState) -> None:
    """
    打印完整的消息链路，用于调试和追踪对话流程

    Args:
        state: 当前状态
    """
    messages = state.get("messages", [])
    logger.info(f"📜 完整消息链路 (共 {len(messages)} 条消息)")
    for i, msg in enumerate(messages, 0):
        logger.debug(
            f"[{i}] 完整内容:\n{msg.model_dump_json(indent=2, ensure_ascii=False)}\n"
        )


############################################################################################################
async def execute_chat_workflow(
    work_flow: CompiledStateGraph[ChatState, Any, ChatState, ChatState],
    context: List[BaseMessage],
    request: HumanMessage,
    llm: AzureChatOpenAI,
) -> List[BaseMessage]:
    """执行聊天工作流并返回所有响应消息

    将聊天历史和用户输入合并后，通过编译好的状态图进行流式处理，
    收集并返回所有生成的消息。ChatState 的创建被封装在函数内部。

    Args:
        work_flow: 已编译的 LangGraph 状态图
        context: 历史消息列表
        request: 用户当前输入的消息
        llm: AzureChatOpenAI LLM 实例

    Returns:
        包含所有生成消息的列表
    """
    ret: List[BaseMessage] = []

    # 在内部构造 ChatState（封装实现细节）
    workflow_state: ChatState = {
        "messages": context + [request],
        "llm": llm,
    }

    try:

        last_state: Optional[ChatState] = None
        async for event in work_flow.astream(workflow_state):
            for value in event.values():
                last_state = value  # 记录最后一个 state

        # 如果存在最后一个 state 且包含 llm_response，则返回它
        if last_state and "llm_response" in last_state:
            assert isinstance(last_state["llm_response"], AIMessage)
            ret = [last_state["llm_response"]]

            # print_full_message_chain(last_state)  # 打印完整消息链路用于调试

    except Exception as e:
        logger.error(
            f"Error executing chat workflow: {e}\n" f"Workflow state: {workflow_state}"
        )
        traceback.print_exc()

    return ret


############################################################################################################
