from langserve import RemoteRunnable
from typing import cast, Any


################################################################################################
def main() -> None:

    # 测试这个地址 lang_serve的
    server_url = "http://localhost:8100/v1/llm_serve/chat/"
    remote: RemoteRunnable[Any, Any] = RemoteRunnable(url=server_url)

    while True:

        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("退出！")
                break

            request_data = {
                "agent_name": "test_agent",
                "user_name": "test_user",
                "input": user_input,
                "chat_history": [],
            }

            # 调用远程服务
            response = remote.invoke(request_data)
            print("Remote response:", cast(str, response["output"]))

        except:
            assert False, "Error in processing user input"


################################################################################################

if __name__ == "__main__":
    main()
