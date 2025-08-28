from dotenv import load_dotenv
from loguru import logger

# 加载 .env 文件中的环境变量
load_dotenv()

import os
import traceback
from typing import Annotated, Any, Dict, List, Optional

from langchain.schema import HumanMessage
from langchain_core.messages import BaseMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import SecretStr
from typing_extensions import TypedDict


# 全局Azure OpenAI GPT实例（懒加载单例）
_global_azure_openai_gpt_llm: Optional[AzureChatOpenAI] = None


def get_azure_openai_gpt_llm() -> AzureChatOpenAI:
    """
    获取全局Azure OpenAI GPT实例（懒加载单例模式）

    Returns:
        AzureChatOpenAI: 配置好的Azure OpenAI GPT实例

    Raises:
        ValueError: 当AZURE_OPENAI_API_KEY环境变量未设置时
    """
    global _global_azure_openai_gpt_llm

    if _global_azure_openai_gpt_llm is None:
        logger.info("🤖 初始化全局Azure OpenAI GPT实例...")

        # 检查必需的环境变量
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")

        if not azure_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set")

        if not azure_api_key:
            raise ValueError("AZURE_OPENAI_API_KEY environment variable is not set")

        _global_azure_openai_gpt_llm = AzureChatOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=SecretStr(azure_api_key),
            azure_deployment="gpt-4o",
            api_version="2024-02-01",
            temperature=0.7,
        )

        logger.success("🤖 全局DeepSeek LLM实例创建完成")

    return _global_azure_openai_gpt_llm


############################################################################################################
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


############################################################################################################
def create_compiled_stage_graph(
    node_name: str,
) -> CompiledStateGraph[State, Any, State, State]:
    assert node_name != "", "node_name is empty"

    def invoke_azure_chat_openai_llm_action(
        state: State,
    ) -> Dict[str, List[BaseMessage]]:

        try:
            llm = get_azure_openai_gpt_llm()
            assert llm is not None, "Failed to get Azure OpenAI GPT instance"
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


############################################################################################################
def main() -> None:

    # 聊天历史
    chat_history_state: State = {"messages": []}

    # 生成聊天机器人状态图
    compiled_stage_graph = create_compiled_stage_graph("azure_chat_openai_chatbot_node")

    while True:

        try:

            user_input = input("User: ")
            if user_input.lower() in ["/quit", "/exit", "/q"]:
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

            logger.debug("*" * 50)
            for message in chat_history_state["messages"]:
                if isinstance(message, HumanMessage):
                    logger.info(f"User: {message.content}")
                else:
                    logger.success(f"Azure-OpenAI-GPT4o: {message.content}")

        except Exception as e:
            logger.error(
                f"Error in processing user input = {e}\n"
                f"Traceback: {traceback.format_exc()}"
            )


############################################################################################################
if __name__ == "__main__":
    main()
