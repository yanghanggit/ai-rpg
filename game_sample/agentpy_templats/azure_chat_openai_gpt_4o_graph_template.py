import os
from typing import Annotated, Final, cast, Dict, List, Union, Any, override
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

############################################################################################################
PORT: Final[int] = int("""<%PORT>""")
############################################################################################################
TEMPERATURE: Final[float] = float("""<%TEMPERATURE>""")
############################################################################################################
API: Final[str] = """<%API>"""
############################################################################################################
SYSTEM_PROMPT: Final[str] = f"""<%SYSTEM_PROMPT_CONTENT>"""


############################################################################################################
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


############################################################################################################
class RequestModel(BaseModel):
    input: str = ""
    chat_history: List[Union[HumanMessage, AIMessage, FunctionMessage]] = []

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
class ResponseModel(BaseModel):
    output: str = ""

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
def generate_chatbot_state_compiled_graph() -> CompiledStateGraph:

    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=SecretStr(str(os.getenv("AZURE_OPENAI_API_KEY"))),
        azure_deployment="gpt-4o",
        api_version="2024-02-01",
        temperature=TEMPERATURE,
    )

    def chatbot(state: State) -> Dict[str, List[BaseMessage]]:
        return {"messages": [llm.invoke(state["messages"])]}

    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.set_entry_point("chatbot")
    graph_builder.set_finish_point("chatbot")
    compiled_chatbot_state_graph: CompiledStateGraph = graph_builder.compile()
    return compiled_chatbot_state_graph


############################################################################################################
def stream_graph_updates(
    state_compiled_graph: CompiledStateGraph,
    system_state: State,
    chat_history_state: State,
    user_input_state: State,
) -> List[BaseMessage]:

    ret: List[BaseMessage] = []

    merged_message_context = {
        "messages": system_state["messages"]
        + chat_history_state["messages"]
        + user_input_state["messages"]
    }

    for event in state_compiled_graph.stream(merged_message_context):
        for value in event.values():
            ai_messages: List[AIMessage] = cast(List[AIMessage], value["messages"])
            print("Assistant:", ai_messages[-1].content)
            ret.extend(ai_messages)

    return ret


############################################################################################################
class ChatExecutor(Runnable[Dict[str, Any], Dict[str, Any]]):

    def __init__(self, state_compiled_graph: CompiledStateGraph) -> None:
        super().__init__()
        self._state_compiled_graph = state_compiled_graph

    def _process_chat_request(self, request: RequestModel) -> ResponseModel:

        # 系统提示词
        system_state: State = {"messages": [SystemMessage(content=SYSTEM_PROMPT)]}

        # 聊天历史
        chat_history_state: State = {
            "messages": [message for message in request.chat_history]
        }

        # 用户输入
        user_input_state: State = {"messages": [HumanMessage(content=request.input)]}

        # 获取回复
        update_messages = stream_graph_updates(
            state_compiled_graph=self._state_compiled_graph,
            system_state=system_state,
            chat_history_state=chat_history_state,
            user_input_state=user_input_state,
        )

        # 返回
        if len(update_messages) > 0:
            return ResponseModel(output=cast(str, update_messages[-1].content))
        return ResponseModel(output="")

    @override
    def invoke(
        self, input: Dict[str, Any], config: RunnableConfig | None = None, **kwargs: Any
    ) -> Dict[str, Any]:
        # 处理请求
        response_model = self._process_chat_request(RequestModel(**input))
        return response_model.model_dump()


############################################################################################################
def main() -> None:
    import uvicorn

    app = FastAPI(
        title="agent app",
        version="0.0.1",
        description="chat",
    )

    # 如果api以/结尾，就将尾部的/去掉，不然add_routes会出错.
    api = str(API)
    if api.endswith("/"):
        api = api[:-1]

    add_routes(
        app,
        ChatExecutor(state_compiled_graph=generate_chatbot_state_compiled_graph()),
        path=api,
    )
    uvicorn.run(app, host="localhost", port=PORT)


############################################################################################################
def test() -> None:

    # 系统提示词
    system_state: State = {"messages": [SystemMessage(content=SYSTEM_PROMPT)]}

    # 聊天历史
    chat_history_state: State = {"messages": []}

    # 生成聊天机器人状态图
    chatbot_state_compiled_graph = generate_chatbot_state_compiled_graph()

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
                state_compiled_graph=chatbot_state_compiled_graph,
                system_state=system_state,
                chat_history_state=chat_history_state,
                user_input_state=user_input_state,
            )

            # 测试用：记录上下文。
            chat_history_state["messages"].extend(user_input_state["messages"])
            chat_history_state["messages"].extend(update_messages)

        except:
            assert False, "Error in processing user input"
            break


############################################################################################################
if __name__ == "__main__":
    main()
    # test()
