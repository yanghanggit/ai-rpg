from typing import List, Union
from fastapi import FastAPI
from langchain.agents import AgentExecutor, create_openai_functions_agent, tool
from langchain.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langserve import add_routes
from langserve.pydantic_v1 import BaseModel, Field
from tools.extract_md_content import extract_md_content
from langserve import RemoteRunnable

player_md = extract_md_content("/actor/player/player.md")
# npc_dialogue_rules = extract_md_content("/actor/npc/npc_dialogue_rules.md")
# {npc_dialogue_rules}

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"""
            {player_md}\n
            """,
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

llm = ChatOpenAI(model="gpt-4-turbo-preview")

def call_agent(input_val, npc_agent, chat_history):
    response = npc_agent.invoke({"input": input_val, "chat_history": chat_history})
    chat_history.extend([HumanMessage(content=input_val), AIMessage(content=response['output'])])
    return response['output']

@tool
def call_task_agent(words: str) -> str:
    """User talk to npc."""
    #return "talk_to_npc"
    task_agent = RemoteRunnable("http://localhost:8005/actor/task/")
    task_agent = call_agent(words, task_agent, [])
    return task_agent

# @tool
# def talk_to_scene(words: str) -> str:
#     """User talk to iterm."""
#     return "talk_to_scene"
#     # scene_agent = RemoteRunnable("http://localhost:8002/actor/npc/house/")
#     # scene_response = talk_to_agent(words, scene_agent, [])
#     # return scene_response

# @tool
# def interact_to_item(words: str) -> str:
#     """User interact to item."""
#     return "interact_to_item"
#     # if "地图" in words:
#     #     npc_agent = RemoteRunnable("http://localhost:8001/actor/npc/elder/")
#     #     talk_to_agent("勇者获得了地图", npc_agent, [])
#     #     return "成功获取地图"
#     # return " "

# @tool
# def talk_to_self(words: str) -> str:
#     """User talk to self."""
#     return "talk_to_self"
#     #return "自言自语道" + "或许可以环顾四周找找有没有什么东西"

@tool
def how_feel_about_it(words: str) -> str:
    """"""

    
tools = [call_task_agent]

agent = create_openai_functions_agent(llm, tools, prompt)

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
    path="/actor/player"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8008)


#"http://localhost:8008/actor/player/"