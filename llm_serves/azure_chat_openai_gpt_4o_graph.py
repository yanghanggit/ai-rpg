import sys
from pathlib import Path
import threading

sys.path.append(str(Path(__file__).resolve().parent.parent))
import os
import traceback
from typing import Annotated, cast, Dict, List, Union, Any, override
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage
from pydantic import SecretStr
from langchain.schema import AIMessage, HumanMessage, SystemMessage, FunctionMessage
from fastapi import FastAPI
from pydantic import BaseModel
from langserve import (
    add_routes,
)
from langchain.schema.runnable import Runnable, RunnableConfig
from langgraph.graph.state import CompiledStateGraph
import traceback
from pathlib import Path
from llm_serves.config import (
    AgentStartupConfiguration,
)


############################################################################################################
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


############################################################################################################
class RequestModel(BaseModel):
    agent_name: str = ""
    user_name: str = ""
    input: str = ""
    chat_history: List[
        Union[SystemMessage, HumanMessage, AIMessage, FunctionMessage]
    ] = []

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
class ResponseModel(BaseModel):
    agent_name: str = ""
    user_name: str = ""
    output: str = ""

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
def _create_compiled_stage_graph(
    node_name: str = "azure_chat_openai_chatbot_node", temperature: float = 0.7
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

            # 1) 打印异常信息本身
            print(f"invoke_azure_chat_openai_llm_action, An error occurred: {e}")

            # 2) 打印完整堆栈信息，方便进一步排查
            traceback.print_exc()

        # 当出现 Azure 内容过滤的情况，或者其他类型异常时，视需求可在此返回空字符串或者自定义提示。
        return {"messages": [AIMessage(content="")]}

    graph_builder = StateGraph(State)
    graph_builder.add_node(node_name, invoke_azure_chat_openai_llm_action)
    graph_builder.set_entry_point(node_name)
    graph_builder.set_finish_point(node_name)
    return graph_builder.compile()


############################################################################################################
def _stream_graph_updates(
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
            ai_messages: List[AIMessage] = cast(List[AIMessage], value["messages"])
            print("Assistant:", ai_messages[-1].content)
            ret.extend(ai_messages)

    return ret


############################################################################################################
class ChatExecutor(Runnable[Dict[str, Any], Dict[str, Any]]):

    def __init__(self, compiled_state_graph: CompiledStateGraph) -> None:
        super().__init__()
        self._compiled_state_graph = compiled_state_graph

    def _process_chat_request(self, request: RequestModel) -> ResponseModel:

        # 聊天历史
        chat_history_state: State = {
            "messages": [message for message in request.chat_history]
        }

        # 用户输入
        user_input_state: State = {"messages": [HumanMessage(content=request.input)]}

        # 获取回复
        update_messages = _stream_graph_updates(
            state_compiled_graph=self._compiled_state_graph,
            chat_history_state=chat_history_state,
            user_input_state=user_input_state,
        )

        # 返回
        if len(update_messages) > 0:
            return ResponseModel(
                agent_name=request.agent_name,
                user_name=request.user_name,
                output=cast(str, update_messages[-1].content),
            )
        return ResponseModel(
            agent_name=request.agent_name, user_name=request.user_name, output=""
        )

    @override
    def invoke(
        self, input: Dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ) -> Dict[str, Any]:
        # 处理请求
        return self._process_chat_request(RequestModel(**input)).model_dump()


############################################################################################################
def main() -> None:

    if len(sys.argv) < 2:
        print("请提供配置文件路径作为参数")
        sys.exit(1)

    arguments = sys.argv[1:]  # 获取除脚本名称外的所有参数
    print("接收到的参数:", arguments)

    # 读取配置文件
    agent_startup_config_file_path: Path = Path(str(arguments[0]))

    if not agent_startup_config_file_path.exists():
        # 如果文件不存在，打印错误信息并返回
        return

    try:

        config_file_content = agent_startup_config_file_path.read_text(encoding="utf-8")
        agent_startup_config = AgentStartupConfiguration.model_validate_json(
            config_file_content
        )

        if len(agent_startup_config.service_configurations) == 0:
            print("没有找到配置")
            return

        for configuration in agent_startup_config.service_configurations:

            app = FastAPI(
                title=configuration.fast_api_title,
                version=configuration.fast_api_version,
                description=configuration.fast_api_description,
            )

            # 如果api以/结尾，就将尾部的/去掉，不然add_routes会出错.
            api = str(configuration.api)
            if api.endswith("/"):
                api = api[:-1]

            add_routes(
                app,
                ChatExecutor(
                    compiled_state_graph=_create_compiled_stage_graph(
                        "azure_chat_openai_chatbot_node", configuration.temperature
                    )
                ),
                path=api,
            )

            # 这么写就是堵塞的。uvicorn.run(app, host="localhost", port=configuration.port)
            def run_server() -> None:
                # 必须这么写。
                import uvicorn

                uvicorn.run(
                    app,
                    host="localhost",
                    port=configuration.port,
                    # 可选：关闭不必要的日志输出
                    # access_log=False,
                )

            # 创建并启动线程
            thread = threading.Thread(target=run_server)
            thread.daemon = True  # 设置为守护线程，主线程退出时自动终止
            thread.start()

    except Exception as e:
        # logger.error(f"Exception: {e}")
        print(f"Exception: {e}")

    # 主线程继续执行其他逻辑或挂起
    while True:
        pass  # 保持主线程存活，防止子线程退出


############################################################################################################
def _test() -> None:

    # 聊天历史
    chat_history_state: State = {"messages": []}

    # 生成聊天机器人状态图
    compiled_stage_graph = _create_compiled_stage_graph()

    while True:

        try:

            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            # 用户输入
            user_input_state: State = {"messages": [HumanMessage(content=user_input)]}

            # 获取回复
            update_messages = _stream_graph_updates(
                state_compiled_graph=compiled_stage_graph,
                chat_history_state=chat_history_state,
                user_input_state=user_input_state,
            )

            # 测试用：记录上下文。
            chat_history_state["messages"].extend(user_input_state["messages"])
            chat_history_state["messages"].extend(update_messages)

        except Exception as e:
            assert False, f"Error in processing user input = {e}"
            # break


############################################################################################################
if __name__ == "__main__":
    main()
    # _test()
