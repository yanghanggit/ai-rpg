# hi, 我写了一个langgraph的对话机器人，请你看一下，并理解。然后我再提出我的需求

## 代码
```python
import os
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage
from pydantic import SecretStr


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


graph_builder = StateGraph(State)


llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=SecretStr(str(os.getenv("AZURE_OPENAI_API_KEY"))),
    azure_deployment="gpt-4o",
    api_version="2024-02-01",
)


# 定义节点
def chatbot(state: State) -> dict[str, list[BaseMessage]]:
    return {"messages": [llm.invoke(state["messages"])]}


# 构建
graph_builder.add_node("chatbot", chatbot)
graph_builder.set_entry_point("chatbot")
graph_builder.set_finish_point("chatbot")
graph = graph_builder.compile()


def stream_graph_updates(user_input: str) -> None:
    for event in graph.stream({"messages": [("user", user_input)]}):
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)


# 测试
while True:

    try:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        stream_graph_updates(user_input)
    except:
        # fallback if input() is not available
        user_input = "What do you know about LangGraph?"
        print("User: " + user_input)
        stream_graph_updates(user_input)
        break
```




# 针对 流式运行图，即 stream_graph_updates，我有问题。
## 问题1: stream_graph_updates 是无法让agent有‘上下文’的对么？
- 因为我看到，每次调用提交给LLM的prompt只有 {"messages": [("user", user_input)]}。
- 我还有一个疑问：State这个类本身不会将messages的历史记录下来对吧？


# 我的同事有一些旧的代码，我发给你，我认为对后续我提出需求有借鉴意义。这个是比较老的langchain的版本，而且不是langgraph的实现。

## 补充信息
- 我询问了我的同事，他说这叫做langserve。
- 我们公司目前在使用的LLM服务为Azure的OpenAI。

## 代码如下
```python
import sys
import os
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List, Union
from fastapi import FastAPI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langserve import add_routes  # type: ignore
from langserve.pydantic_v1 import BaseModel, Field  # type: ignore
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import SecretStr

PORT: int = 8405
TEMPERATURE: float = 0.7
API: str = """/actor/test_npc"""
SYSTEM_PROMPT: str = """# TestNPC
你扮演这个游戏世界中的一个角色: TestNPC。
## 游戏背景
。。。。。"""

class Input(BaseModel):
    input: str
    chat_history: List[Union[HumanMessage, AIMessage, FunctionMessage]] = Field(
        ...,
        extra={"widget": {"type": "chat", "input": "input", "output": "output"}},
    )


class Output(BaseModel):
    output: str

def main() -> None:

    chat_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                SYSTEM_PROMPT,
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    print(
        f'endpoint:{os.getenv("AZURE_OPENAI_ENDPOINT")}\n key:{os.getenv("AZURE_OPENAI_API_KEY")}'
    )

    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=SecretStr(str(os.getenv("AZURE_OPENAI_API_KEY"))),
        azure_deployment="gpt-4o",
        api_version="2024-02-01",
        temperature=TEMPERATURE,
    )

    @tool
    def debug_tool() -> str:
        """debug"""
        return "Debug tool"

    tools = [debug_tool]

    agent = create_openai_functions_agent(llm, tools, chat_prompt_template)

    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    app = FastAPI(
        title="Chat module",
        version="1.0",
        description="Gen chat",
    )

    add_routes(
        app, agent_executor.with_types(input_type=Input, output_type=Output), path=API
    )

    import uvicorn

    uvicorn.run(app, host="localhost", port=PORT)


if __name__ == "__main__":
    main()
```


# 关于老代码我还有一个问题。关于ChatPromptTemplate的问题。

## 请看如下代码片段，
```python
chat_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                SYSTEM_PROMPT,
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
```

## 我的问题
1. 根据老的代码这个py文件的写法。如果启动，也就是意味着 SYSTEM_PROMPT 设定不会更改。
2. 根据 ChatPromptTemplate.from_messages 的写法。我看到每次调用会有 chat_history 与 input。通过 class Input(BaseModel)。传过来
3. 根据1，2。我们可以认为。agent每次推理的‘上下文’是由 "system", "chat_history",  ("user", "{input}"), "agent_scratchpad" 组成的?


# 好的，我理解了。回到我的代码，这个langgraph的实现。
## 我关注这个函数
```python
def stream_graph_updates(user_input: str) -> None:
```
## 我的问题与需求
- 问题：这个函数是否可以跟老代码中的 ChatPromptTemplate.from_messages 有类似的功能或实现？
    - 这样我可以借鉴老代码的实现，让agent有‘上下文’。
- 请你思考一下，如果可以请回顾langchain与langgraph的开发文档信息。
- 然后给我提出建议如何实现这个功能。


# hi, 我写了langgraph的对话机器人，代码如下，请你看一下，并理解。然后我再提出我的需求

## 代码
```python
import os
from typing import Annotated, Final, cast, Dict, List, Union
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage
from pydantic import SecretStr
from langchain.schema import AIMessage, HumanMessage, SystemMessage, FunctionMessage
from fastapi import FastAPI
from pydantic import BaseModel

############################################################################################################
PORT: Final[int] = int("""<%PORT>""")  # 会在运行时替换为真实的端口号
TEMPERATURE: Final[float] = float("""<%TEMPERATURE>""")  # 会在运行时替换为真实的温度值
API: Final[str] = """<%API>"""  # 会在运行时替换为真实的API路径
SYSTEM_PROMPT: Final[str] = (
    """<%SYSTEM_PROMPT_CONTENT>"""  # 会在运行时替换为真实的系统提示内容
)


############################################################################################################
############################################################################################################
############################################################################################################
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


############################################################################################################
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=SecretStr(str(os.getenv("AZURE_OPENAI_API_KEY"))),
    azure_deployment="gpt-4o",
    api_version="2024-02-01",
    temperature=TEMPERATURE,
)


############################################################################################################
def chatbot(state: State) -> Dict[str, List[BaseMessage]]:
    return {"messages": [llm.invoke(state["messages"])]}


############################################################################################################
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.set_entry_point("chatbot")
graph_builder.set_finish_point("chatbot")
graph = graph_builder.compile()


############################################################################################################
def stream_graph_updates(
    system_state: State,
    chat_history_stage: State,
    user_input: State,
) -> List[BaseMessage]:

    ret: List[BaseMessage] = []

    merged_message_context = {
        "messages": system_state["messages"]
        + chat_history_stage["messages"]
        + user_input["messages"]
    }

    for event in graph.stream(merged_message_context):
        for value in event.values():
            ai_messages: List[AIMessage] = cast(List[AIMessage], value["messages"])
            print("Assistant:", ai_messages[-1].content)
            ret.extend(ai_messages)

    return ret


############################################################################################################
app = FastAPI(
    title="agent app",
    version="0.0.1",
    description="chat",
)


class RequestModel(BaseModel):
    input: str = ""
    chat_history: List[Union[HumanMessage, AIMessage, FunctionMessage]] = []

    class Config:
        arbitrary_types_allowed = True


class ResponseModel(BaseModel):
    output: str = ""

    class Config:
        arbitrary_types_allowed = True


############################################################################################################
@app.post(API, response_model=ResponseModel)
async def handle_post_action(req: RequestModel) -> ResponseModel:

    # 组织历史数据
    system_state: State = {"messages": [SystemMessage(content=SYSTEM_PROMPT)]}
    chat_history_state: State = {"messages": [message for message in req.chat_history]}
    user_input_state: State = {"messages": [HumanMessage(content=req.input)]}

    # 用模型进行推理
    update_messages = stream_graph_updates(
        system_state, chat_history_state, user_input_state
    )

    if len(update_messages) > 0:
        return ResponseModel(output=cast(str, update_messages[-1].content))
    return ResponseModel(output="")


############################################################################################################
def main() -> None:
    import uvicorn

    uvicorn.run(app, host="localhost", port=PORT)


############################################################################################################
def test() -> None:
    system_state: State = {"messages": [SystemMessage(content=SYSTEM_PROMPT)]}
    chat_history_state: State = {"messages": []}

    while True:

        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            user_input_state: State = {"messages": [HumanMessage(content=user_input)]}
            update_messages = stream_graph_updates(
                system_state, chat_history_state, user_input_state
            )

            # 记录上下文。
            chat_history_state["messages"].extend(user_input_state["messages"])
            chat_history_state["messages"].extend(update_messages)

        except:
            assert False, "Error in processing user input"
            break


############################################################################################################
if __name__ == "__main__":
    main()
    # test()
```



# 你是否知道langserve?
## 如果你知道请给我简单介绍下。
## 我的需求
- 我希望以上的代码——fastapi-app, RequestModel, ResponseModel, handle_post_action, main()，这些部分用langserve的方式来实现。
- 如果可以实现，这个python文件作为启动一个服务端。请你给我一个客户端示例，如何调用这个服务端。
- 补充信息：据我所知，langserve 有一个RemoteRunnable的类，可以负责在远程调用服务端。我希望使用这个类。



# 这段代码无法通过严格模式检查
## 请你帮我看一下，我应该如何修改这段代码，使其通过严格模式检查。
```python
class ChatRunnable(Runnable):
    """
    这是一个Runnable类，用于langserve部署。
    input: dict 包含 {"input": str, "chat_history": List[BaseMessage]} 
    output: str (AI回答)
    """
    def invoke(self, input_data: Dict[str, Any]) -> str:
        user_input = input_data.get("input", "")
        chat_history = input_data.get("chat_history", [])

        # 构建state
        system_state: State = {"messages": [SystemMessage(content=SYSTEM_PROMPT)]}
        chat_history_state: State = {"messages": chat_history}
        user_input_state: State = {"messages": [HumanMessage(content=user_input)]}

        # 获取回复
        update_messages = stream_graph_updates(
            system_state, chat_history_state, user_input_state
        )
        if len(update_messages) > 0:
            return update_messages[-1].content
        return ""
```
## 报错信息如下
mypy --strict game_sample/agentpy_templats/azure_chat_openai_gpt_4o_graph_template.py
game_sample/agentpy_templats/azure_chat_openai_gpt_4o_graph_template.py:122: error: Missing type parameters for generic type "Runnable"  [type-arg]
game_sample/agentpy_templats/azure_chat_openai_gpt_4o_graph_template.py:128: error: Signature of "invoke" incompatible with supertype "Runnable"  [override]
game_sample/agentpy_templats/azure_chat_openai_gpt_4o_graph_template.py:128: note:      Superclass:
game_sample/agentpy_templats/azure_chat_openai_gpt_4o_graph_template.py:128: note:          def invoke(self, input: Any, config: RunnableConfig | None = ..., **kwargs: Any) -> Any
game_sample/agentpy_templats/azure_chat_openai_gpt_4o_graph_template.py:128: note:      Subclass:
game_sample/agentpy_templats/azure_chat_openai_gpt_4o_graph_template.py:128: note:          def invoke(self, input_data: dict[str, Any]) -> str
game_sample/agentpy_templats/azure_chat_openai_gpt_4o_graph_template.py:142: error: Incompatible return value type (got "str | list[str | dict[Any, Any]]", expected "str")  [return-value]

## def invoke(self, input_data: Dict[str, Any]) -> str: 这个函数能将传入参数与返回值使用RequestModel与ResponseModel么