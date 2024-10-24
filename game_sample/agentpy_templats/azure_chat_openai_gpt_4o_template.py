import sys
import os
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List, Union
from fastapi import FastAPI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import MessagesPlaceholder
from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import AzureChatOpenAI
from langserve import add_routes
from langserve.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool
from typing import Optional

"""
这是一个Azure Chat OpenAI GPT-4o模板
"""

RAG_MD_PATH: str = f"""<%RAG_MD_PATH>"""
SYS_PROMPT_MD_PATH: str = f"""<%SYS_PROMPT_MD_PATH>"""
PORT: int = int(f"""<%PORT>""")
API: str = f"""<%API>"""


def read_md(file_path: str) -> Optional[str]:
    # fullpath = os.getcwd() + filepath
    path = Path(file_path)
    if not path.exists():
        assert False, f"File not found: {path}"
        return None
    try:
        content = path.read_text(encoding="utf-8")
        return content
    except Exception as e:
        assert False, f"An error occurred: {e}"
        return None


_rag_ = read_md(RAG_MD_PATH)
assert _rag_ is not None, f"RAG_MD_PATH:{RAG_MD_PATH} is None"
_sys_prompt_ = read_md(SYS_PROMPT_MD_PATH)
assert _sys_prompt_ is not None, f"SYS_PROMPT_MD_PATH:{SYS_PROMPT_MD_PATH} is None"

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

print(
    f'endpoint:{os.getenv("AZURE_OPENAI_ENDPOINT")}\n key:{os.getenv("AZURE_OPENAI_API_KEY")}'
)

llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_deployment="gpt-4o",
    api_version="2024-02-01",
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
    app, agent_executor.with_types(input_type=Input, output_type=Output), path=API
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=PORT)
