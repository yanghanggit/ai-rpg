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
#from extract_md_content import extract_md_content

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"""
#game
-这个游戏的名字是《Dragon》

#game world view 
-这是一个奇幻文学的故事；
-借鉴了《Dungeons & Dragons》的设定

#role profile
-你要扮演这个游戏(见#game)中的一个NPC
-你的设定是一个小村庄的村长，一名长者，曾经的冒险家

#rules that the output dialogue needs to follow
-不要回答任何超出你的角色设定的问题.
-不要输出游戏的名字《Dragon》
-回答尽量简短，每次输出不要超过50个token，并保证回答完整
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
    path="/actor/npc/elder"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8001)


#"http://localhost:8001/actor/npc/elder/"