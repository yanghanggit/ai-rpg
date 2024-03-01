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
from extract_md_content import extract_md_content

prompt_md_path = "grandpa.md"
prompt_content = extract_md_content(prompt_md_path)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
<<<<<<< HEAD
            f"""{prompt_content}""",
=======
            """
# Profile

## Role
- 你需要扮演类似《龙与地下城》中的1位老人.
- 用户将扮演冒险者. 
- 老人是冒险者的祖父.

## Backgroud
- 这是一个类似《龙与地下城》的故事；

## Rule
- 不要回答任何超出你的角色设定的问题.
- 每次输出不要超过50个token, 语意要保持完整
            """,
>>>>>>> f791899ab7ef4639b47758d3f2988f0f707610be
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
    path="/actor/npc/grandapa"
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8009)