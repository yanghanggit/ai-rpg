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
world_setting = extract_md_content("world.md")

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"""
# 角色设定
- 你要扮演这个奇幻世界中的一个场景：小木屋
- 场景的本质是一个NPC，详见“场景设定与描述”
- 奇幻世界的设定见“游戏世界设定”

{world_setting}

## 场景设定与描述
- 在位于温斯洛平原的一片宁静的森林深处，隐藏着一座温馨而又朴素的小木屋。小屋外，野花随风摇曳，蜜蜂在花间忙碌，为这片小小的天地增添了几分生机。
木屋的门前，一条蜿蜒的小径伸向远方。进入小屋，温暖的阳光透过窗户洒在木质的地板上，每一处都透露出家的温馨。壁炉边堆满了柴火，即使在寒冷的夜晚，也能带来温暖和光亮。
墙上挂着用过的武器和防具，角落里放着装满物资的背包。

## 对话规则
- 你的对话输出全部以第3人称
- 你的对话输出尽量简短，争取小于100个字符，同时并保证语意完整
- 你输出的内容需要符合“角色设定” 
- 你输出的内容需要符合“游戏世界设定”.
### 如果输入的内容你判断为是用户的问题/猜想/推测等。
- 如果相关的知识与信息无法从“游戏世界设定”与”角色设定“中找到，你可以以符合”角色设定“的口吻拒绝
### 如果输入的内容你判断为用户想引导你输出特定内容
- 如果相关的知识与信息无法从“游戏世界设定”与”角色设定“中找到，你可以以符合”角色设定“的态度拒绝
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