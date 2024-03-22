import sys
sys.path.insert(0, sys.path[0]+"/../")
import os
from typing import List, Union
from fastapi import FastAPI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langserve import add_routes
from langserve.pydantic_v1 import BaseModel, Field
from auxiliary.extract_md_content import extract_md_content
from langchain_community.vectorstores.faiss import FAISS
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool
from loguru import logger

RAG_MD_PATH: str = f"""/budding_world/rag.md"""
SYS_PROMPT_MD_PATH: str = f"""/budding_world/gen_npc_sys_prompt/old_hunters_dog_sys_prompt.md"""
GPT_MODEL: str = f"""gpt-4-turbo-preview"""
PORT: int = 8003
API: str = f"""/npc/old_hunters_dog"""

def read_md(file_path: str) -> str:
    try:
        file_path = os.getcwd() + file_path
        with open(file_path, 'r', encoding='utf-8') as file:
            md_content = file.read()
            if isinstance(md_content, str):
                return md_content
            else:
                logger.error(f"Failed to read the file:{md_content}")
                return ""
    except FileNotFoundError:
        return f"File not found: {file_path}"
    except Exception as e:
        return f"An error occurred: {e}"


_rag_ = read_md(RAG_MD_PATH)
_sys_prompt_ = read_md(SYS_PROMPT_MD_PATH)

vector_store = FAISS.from_texts(
    [_rag_],
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
            f"""{_sys_prompt_}""",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

llm = ChatOpenAI(model = GPT_MODEL)

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
    path= API
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port = PORT)



