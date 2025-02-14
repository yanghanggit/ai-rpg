from typing import List, Dict, Union
from agent.lang_serve_system import LangServeSystem
from agent.chat_request_handler import ChatRequestHandler
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


###########################################################################################################################
async def _test_gather() -> None:

    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    lang_serve_system = LangServeSystem(name="test_agent")
    lang_serve_system.add_remote_runnable(url=server_url)

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
    await lang_serve_system.gather(request_handlers=request_handlers)

    for request_handler in request_handlers:
        print(
            f"Agent: {request_handler._name}, Response: {request_handler.response_content}"
        )


###########################################################################################################################
async def _test_chat_history() -> None:

    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    lang_serve_system = LangServeSystem(name="test_agent")
    lang_serve_system.add_remote_runnable(url=server_url)

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
            lang_serve_system.handle(request_handlers=[chat_request_handler])
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(
                AIMessage(content=chat_request_handler.response_content)
            )

            for msg in chat_history:
                print(msg.content)

        except:
            assert False, "Error in processing user input"


###########################################################################################################################
async def main() -> None:

    # 测试消息
    human_message = HumanMessage(content="human message")
    print(human_message.model_dump_json())

    # 测试并发
    await _test_gather()

    # 测试聊天历史
    await _test_chat_history()


###########################################################################################################################

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
