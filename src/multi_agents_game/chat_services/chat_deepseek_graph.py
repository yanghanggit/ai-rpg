from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import traceback
from typing import Annotated, Any, Dict, List

from langchain.schema import HumanMessage
from langchain_core.messages import BaseMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr
from typing_extensions import TypedDict


############################################################################################################
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


############################################################################################################
def create_compiled_stage_graph(
    node_name: str, temperature: float
) -> CompiledStateGraph[State, Any, State, State]:
    assert node_name != "", "node_name is empty"

    # 检查必需的环境变量
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")

    if not deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY environment variable is not set")

    llm = ChatDeepSeek(
        api_key=SecretStr(deepseek_api_key),
        model="deepseek-chat",
        temperature=temperature,
    )

    def invoke_deepseek_llm_action(
        state: State,
    ) -> Dict[str, List[BaseMessage]]:

        try:
            return {"messages": [llm.invoke(state["messages"])]}
        except Exception as e:
            logger.error(f"Error invoking DeepSeek LLM: {e}\n" f"State: {state}")
            traceback.print_exc()
            return {
                "messages": []
            }  # 当出现内容过滤的情况，或者其他类型异常时，视需求可在此返回空字符串或者自定义提示。

    graph_builder = StateGraph(State)
    graph_builder.add_node(node_name, invoke_deepseek_llm_action)
    graph_builder.set_entry_point(node_name)
    graph_builder.set_finish_point(node_name)
    return graph_builder.compile()  # type: ignore[return-value]


############################################################################################################
def stream_graph_updates(
    state_compiled_graph: CompiledStateGraph[State, Any, State, State],
    chat_history_state: State,
    user_input_state: State,
) -> List[BaseMessage]:

    ret: List[BaseMessage] = []

    merged_message_context: State = {
        "messages": chat_history_state["messages"] + user_input_state["messages"]
    }

    for event in state_compiled_graph.stream(merged_message_context):
        for value in event.values():
            ret.extend(value["messages"])

    return ret
