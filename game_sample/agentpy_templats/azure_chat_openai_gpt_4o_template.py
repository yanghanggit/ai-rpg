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
from langserve import add_routes  # type: ignore
from langserve.pydantic_v1 import BaseModel, Field  # type: ignore
from langchain_core.tools import tool
from langchain_core.pydantic_v1 import SecretStr

"""
这是一个Azure Chat OpenAI GPT-4o模板
"""
############################################################################################################
############################################################################################################
############################################################################################################
PORT: int = int("""<%PORT>""")
TEMPERATURE: float = float("""<%TEMPERATURE>""")
############################################################################################################
############################################################################################################
############################################################################################################
API: str = """<%API>"""
############################################################################################################
############################################################################################################
############################################################################################################
SYSTEM_PROMPT: str = """
<%SYSTEM_PROMPT_CONTENT>
"""
############################################################################################################
############################################################################################################
############################################################################################################
RAG_CONTENT: str = """
<%RAG_CONTENT>
"""


############################################################################################################
############################################################################################################
############################################################################################################
class Input(BaseModel):
    input: str
    chat_history: List[Union[HumanMessage, AIMessage, FunctionMessage]] = Field(
        ...,
        extra={"widget": {"type": "chat", "input": "input", "output": "output"}},
    )


class Output(BaseModel):
    output: str


############################################################################################################
############################################################################################################
############################################################################################################


def main() -> None:

    chat_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                SYSTEM_PROMPT,
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
        api_key=SecretStr(str(os.getenv("AZURE_OPENAI_API_KEY"))),
        azure_deployment="gpt-4o",
        api_version="2024-02-01",
        temperature=TEMPERATURE,
    )

    @tool
    def debug_tool() -> str:
        """debug"""
        return "Debug tool"

    tools = [debug_tool]

    agent = create_openai_functions_agent(llm, tools, chat_prompt_template)

    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

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
