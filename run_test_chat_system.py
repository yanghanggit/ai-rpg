from typing import Dict, List, Union
from loguru import logger
from llm_serves.chat_system import ChatSystem
from llm_serves.chat_request_handler import ChatRequestHandler
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import requests
from llm_serves.chat_request_protocol import (
    ChatRequestModel,
    ChatResponseModel,
)


###########################################################################################################################
async def _test_gather() -> None:

    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    chat_system = ChatSystem(
        name="test_agent", user_name="yh", localhost_urls=[server_url]
    )

    test_prompt_data: Dict[str, str] = {
        "agent1": "你好!你是谁",
        "agent2": "德国的首都在哪里",
        "agent3": "凯撒是哪国人？",
    }

    # 添加请求处理器
    request_handlers: List[ChatRequestHandler] = []
    for agent_name, prompt in test_prompt_data.items():
        request_handlers.append(
            ChatRequestHandler(name=agent_name, prompt=prompt, chat_history=[])
        )

    # 并发
    await chat_system.gather(request_handlers=request_handlers)

    for request_handler in request_handlers:
        print(
            f"Agent: {request_handler._name}, Response: {request_handler.response_content}"
        )


###########################################################################################################################
async def _test_chat_history() -> None:

    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    chat_system = ChatSystem(
        name="test_agent", user_name="yh", localhost_urls=[server_url]
    )

    chat_history: List[Union[SystemMessage, HumanMessage, AIMessage]] = []
    chat_history.append(
        SystemMessage(content="你需要扮演一个海盗与我对话，要用海盗的语气哦！")
    )

    while True:

        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("退出！")
                break

            chat_request_handler = ChatRequestHandler(
                name="yh", prompt=user_input, chat_history=chat_history
            )
            chat_system.handle(request_handlers=[chat_request_handler])
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(
                AIMessage(content=chat_request_handler.response_content)
            )

            for msg in chat_history:
                print(msg.content)

        except Exception as e:
            logger.error(f"Exception: {e}")
            assert False, f"Error in processing user input = {e}"


###########################################################################################################################
async def _send_chat_request() -> None:

    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    request_data = ChatRequestModel(
        agent_name="test_agent",
        user_name="yh",
        input="你好！你是谁？",
        chat_history=[
            SystemMessage(content="你需要扮演一个海盗与我对话，要用海盗的语气哦！")
        ],
    )

    response = requests.post(
        server_url,
        json=request_data.model_dump(),
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        response_data = response.json()
        logger.debug(f"Response: {response_data}")

        response_model = ChatResponseModel.model_validate(response_data)
        logger.debug(f"Response Model: {response_model.model_dump_json()}")

    else:
        logger.error(f"Error: {response.status_code}, {response.text}")


###########################################################################################################################
async def main() -> None:

    #
    await _send_chat_request()


###########################################################################################################################

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
