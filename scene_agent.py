from typing import Any, List, Union
from fastapi import FastAPI
from langchain.agents import AgentExecutor, tool
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langserve import add_routes
from langserve.pydantic_v1 import BaseModel, Field

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"""
#Game
-这个游戏的名字是《Dragon》

#The world view of the game 
-这是一个奇幻文学的故事；
-借鉴了《Dungeons & Dragons》(D&D)的设定

#Your role setting and introduction
-你要扮演这个游戏(见#game)中的一个场景
-你的设定是一个村庄中的小木屋，描述见#Scene description

#Scene description
在一片宁静的森林深处，隐藏着一座温馨而又朴素的小木屋。小屋外，野花随风摇曳，蜜蜂在花间忙碌，为这片小小的天地增添了几分生机。
木屋的门前，一条蜿蜒的小径伸向远方。进入小屋，温暖的阳光透过窗户洒在木质的地板上，每一处都透露出家的温馨。壁炉边堆满了柴火，即使在寒冷的夜晚，也能带来温暖和光亮。
墙上挂着用过的武器和防具，角落里放着装满物资的背包。

#Rules that the output dialogue needs to follow
-你的输出全部以第3人称
-不要输出任何超出你的设定的问题.
-不要输出游戏的名字《Dragon》
-输出尽量简短，每次输出不要超过50个token，并保证语意完整
            """,
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

llm = ChatOpenAI(model="gpt-4-turbo-preview")

@tool
def never_call_this_function() -> str:
    """Never call this function!!!"""
    return "chat module"

tools = [never_call_this_function]

llm_with_tools = llm.bind_functions(tools)

agent = (
    {
        "input": lambda x: x["input"],
        "agent_scratchpad": lambda x: format_to_openai_tool_messages(
            x["intermediate_steps"]
        ),
        "chat_history": lambda x: x["chat_history"],
    }
    | prompt
    | llm_with_tools
    | OpenAIToolsAgentOutputParser()
)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

app = FastAPI(
    title="Chat module",
    version="1.0",
    description="Gen chat",
)

class Input(BaseModel):
    input: str
    chat_history: List[Union[HumanMessage, AIMessage, FunctionMessage]] = Field(
        ...,
        extra={"widget": {"type": "chat", "input": "input", "output": "output"}},
    )

class Output(BaseModel):
    output: str

add_routes(
    app,
    agent_executor.with_types(input_type=Input, output_type=Output),
    path="/actor/npc/house"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8002)


#"http://localhost:8002/actor/npc/house/"