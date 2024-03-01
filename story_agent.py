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
- 你将扮演一个龙与地下城故事的作者.

## Background
- 这个故事中有一个老人和一个年轻人.
- 老人是年轻人的祖父.
- 年轻人知道了地下城有一把绝世的宝剑,所以总是想要探索无限可能的地下城,拿到宝剑.

## Rule
- 你需要设计一个充满危险和有趣的故事.
- 根据输入的话,去展开描写更丰富的背景故事.
- 把故事中的“年轻人”换成“你”去描述.
- 不要给出任何选项.
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