from langchain_core.pydantic_v1 import BaseModel, Field
import json
from langchain_core.agents import AgentActionMessageLog, AgentFinish
from langchain.agents import AgentExecutor, tool
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from fastapi import FastAPI
from typing import Any
from langserve import add_routes

class Evaluate(BaseModel):
    """Evaluate based on prompt"""
    result: int = Field(description="Final evaluate result.")

def parse(output):
    if "function_call" not in output.additional_kwargs:
        return AgentFinish(return_values={"output": output.content}, log=output.content)
    
    function_call = output.additional_kwargs["function_call"]
    name = function_call["name"]
    inputs = json.loads(function_call["arguments"])

    if name == "Evaluate":
        return AgentFinish(return_values={"output": inputs["result"]}, log=str(function_call))
    else:
        return AgentActionMessageLog(
            tool=name, tool_input=inputs, log="", message_log=[output]
        )
    
prompt = ChatPromptTemplate.from_messages(
    [
        ("system",
        """
# Profile

## Role
- 你需要负责对输入的话进行评估,评估的标准必须参考Rule;

## Background
- 一个冒险者与他的祖父之间的对话,冒险者希望说服祖父让他出村去地下城探索.
- 祖父非常担心冒险者的安全.

## Rule
- 每次从冒险者和祖父的对话中评估出祖父的放心程度.
- 根据对话的效果给出不同数值的放心程度.
- 放心程度的范围是[1-10].
    """),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)

llm_with_tools = llm.bind_functions([Evaluate])

@tool
def debug_log() -> str:
    """Just for debug"""
    return "numerical output agent"

tools = [debug_log]

agent = (
    {
        "input": lambda x: x["input"],
        "agent_scratchpad": lambda x: format_to_openai_function_messages(
            x["intermediate_steps"]
        ),
    }
    | prompt
    | llm_with_tools
    | parse
)

agent_executor = AgentExecutor(tools=tools, agent=agent, verbose=True)

app = FastAPI(
    title="Evalaute Module",
    version="1.0",
    description="Evaluate based on prompt",
)

class Input(BaseModel):
    input: str

class Output(BaseModel):
    output: Any

add_routes(
    app,
    agent_executor.with_types(input_type=Input, output_type=Output),
    path="/system/evaluate"
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8007)

