import sys
sys.path.insert(0, sys.path[0]+"/../")
import os
from typing import List, Union
from fastapi import FastAPI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langserve import add_routes
from langserve.pydantic_v1 import BaseModel, Field
from loguru import logger
from langchain_core.tools import tool

RAG_MD_PATH: str = f"""<%RAG_MD_PATH>"""
SYS_PROMPT_MD_PATH: str = f"""<%SYS_PROMPT_MD_PATH>"""
#GPT_MODEL: str = f"""<%GPT_MODEL>"""
PORT: int = <%PORT>
API: str = f"""<%API>"""

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

print(f'endpoint:{os.getenv("AZURE_OPENAI_ENDPOINT")}\n key:{os.getenv("AZURE_OPENAI_API_KEY")}')

llm = AzureChatOpenAI(
    azure_endpoint= os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key= os.getenv("AZURE_OPENAI_API_KEY"),
    azure_deployment="gpt-4o",
    api_version="2024-02-01"
)

@tool
def debug_tool():
    """debug"""
    return "Debug tool"

tools = [debug_tool]

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
