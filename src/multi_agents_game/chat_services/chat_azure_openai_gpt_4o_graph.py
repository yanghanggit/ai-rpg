import sys
from pathlib import Path

from loguru import logger

sys.path.append(str(Path(__file__).resolve().parent.parent))
import os
import traceback
from typing import Annotated, Dict, List
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage
from pydantic import SecretStr
from langchain.schema import HumanMessage
from langgraph.graph.state import CompiledStateGraph


############################################################################################################
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


############################################################################################################
def create_compiled_stage_graph(
    node_name: str, temperature: float
) -> CompiledStateGraph:
    assert node_name != "", "node_name is empty"

    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=SecretStr(str(os.getenv("AZURE_OPENAI_API_KEY"))),
        azure_deployment="gpt-4o",
        api_version="2024-02-01",
        temperature=temperature,
    )

    def invoke_azure_chat_openai_llm_action(
        state: State,
    ) -> Dict[str, List[BaseMessage]]:

        try:
            return {"messages": [llm.invoke(state["messages"])]}
        except Exception as e:
            logger.error(
                f"Error invoking Azure Chat OpenAI LLM: {e}\n" f"State: {state}"
            )
            traceback.print_exc()
            return {
                "messages": []
            }  # 当出现 Azure 内容过滤的情况，或者其他类型异常时，视需求可在此返回空字符串或者自定义提示。

    graph_builder = StateGraph(State)
    graph_builder.add_node(node_name, invoke_azure_chat_openai_llm_action)
    graph_builder.set_entry_point(node_name)
    graph_builder.set_finish_point(node_name)
    return graph_builder.compile()


############################################################################################################
def stream_graph_updates(
    state_compiled_graph: CompiledStateGraph,
    chat_history_state: State,
    user_input_state: State,
) -> List[BaseMessage]:

    ret: List[BaseMessage] = []

    merged_message_context = {
        "messages": chat_history_state["messages"] + user_input_state["messages"]
    }

    for event in state_compiled_graph.stream(merged_message_context):
        for value in event.values():
            ret.extend(value["messages"])

    return ret


############################################################################################################
def main() -> None:

    # 聊天历史
    chat_history_state: State = {"messages": []}

    # 生成聊天机器人状态图
    compiled_stage_graph = create_compiled_stage_graph(
        "azure_chat_openai_chatbot_node", 0.7
    )

    while True:

        try:

            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            # 用户输入
            user_input_state: State = {"messages": [HumanMessage(content=user_input)]}

            # 获取回复
            update_messages = stream_graph_updates(
                state_compiled_graph=compiled_stage_graph,
                chat_history_state=chat_history_state,
                user_input_state=user_input_state,
            )

            # 测试用：记录上下文。
            chat_history_state["messages"].extend(user_input_state["messages"])
            chat_history_state["messages"].extend(update_messages)

        except Exception as e:
            assert False, f"Error in processing user input = {e}"


############################################################################################################
if __name__ == "__main__":
    main()
