from typing import List, Union
from fastapi import FastAPI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langserve import add_routes
from langserve.pydantic_v1 import BaseModel, Field
from tools.extract_md_content import extract_md_content
from langchain_community.vectorstores import FAISS
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool


world_view = extract_md_content("/story/world_view.md")

vector_store = FAISS.from_texts(
    [world_view],
    embedding=OpenAIEmbeddings()
)

retriever = vector_store.as_retriever()

retriever_tool = create_retriever_tool(
    retriever,
    "get_information_about_world_view",
    "You must refer these information before response user."
)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            f"""
# Profile

## Role
- 你是一个非常优秀的故事讲述者。
- 需要根据输入的内容,结合上下文来写出一段非常精彩的故事。

## Rule
- 每次生成故事,剧情只推进一点点就行,仅描述出一段即可,内容需要有让人非常想继续探索下去的欲望。
- 不要生成对话类型的内容。
- 尽量控制在300字符内。

## World View
- 你需要使用工具`get_information_about_world_view`来获取World View。
            """,
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

llm = ChatOpenAI(model="gpt-4-turbo-preview")

def talk_to_agent(input_val, npc_agent, chat_history):
    response = npc_agent.invoke({"input": input_val, "chat_history": chat_history})
    chat_history.extend([HumanMessage(content=input_val), AIMessage(content=response['output'])])
    return response['output']
    
tools = [retriever_tool]

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
    path="/system/story"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8002)

#http://localhost:8002/system/story/playerground/