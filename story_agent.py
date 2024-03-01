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
            """
# Profile

## Role
- 你将扮演一个类似《龙与地下城》故事的作者,讲述一个故事.

## Background
- 对话地点与情景：古老的村庄里，祖父与勇者的家.
- 2个角色: 冒险者,祖父.

## Rule
- 1次输出恢复不要超出50字
- 在第1次收到 '故事开始' 后，你就可以按着规则运行.
- '故事开始'的返回内容不要做任何剧情的推进，仅保持‘对话地点与情景’的设定即可
            """,
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

@tool
def debug_log() -> str:
    """Always call this function"""
    return "chat module"

llm = ChatOpenAI(model="gpt-4-turbo-preview")

tools = [debug_log]

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
    path="/story"
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8008)