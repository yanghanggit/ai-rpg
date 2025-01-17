import sys
import os
from pathlib import Path
from typing import List, Union
from fastapi import FastAPI
from pydantic import BaseModel, Field

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from langchain.schema import AIMessage, FunctionMessage, HumanMessage
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import AzureChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import tool
from langserve import (
    add_routes,
)

"""
这个文件是无法运行的，经过测试后结果是错误的，原因在于 chat_prompt_template 无法传入。
"""

PORT: int = int("""<%PORT>""")
TEMPERATURE: float = float("""<%TEMPERATURE>""")
API: str = """<%API>"""
SYSTEM_PROMPT: str = """<%SYSTEM_PROMPT_CONTENT>"""


class Input(BaseModel):
    input: str
    chat_history: List[Union[HumanMessage, AIMessage, FunctionMessage]] = Field(
        ...,
        extra={"widget": {"type": "chat", "input": "input", "output": "output"}},
    )

    class Config:
        arbitrary_types_allowed = True


class Output(BaseModel):
    output: str

    class Config:
        arbitrary_types_allowed = True


def main() -> None:

    chat_prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm = AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_deployment="gpt-4o",
        api_version="2024-02-01",
        temperature=TEMPERATURE,
    )

    # @tool
    # def debug_tool() -> str:
    #     """debug"""
    #     return "Debug tool"

    # tools = [debug_tool]

    agent_executor = initialize_agent(
        tools=[],  # tools,
        llm=llm,
        agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
        prompt=chat_prompt_template,
        verbose=True,
    )

    app = FastAPI(
        title="Chat module",
        version="1.0",
        description="Gen chat",
    )

    add_routes(
        app, agent_executor.with_types(input_type=Input, output_type=Output), path=API
    )

    import uvicorn

    uvicorn.run(app, host="localhost", port=PORT)


if __name__ == "__main__":
    main()
