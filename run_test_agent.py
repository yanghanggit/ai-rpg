from langserve import RemoteRunnable
from typing import cast, Any


################################################################################################
def main() -> None:

    # http://localhost:8701/world_system/world_appearance_system/
    # http://localhost:8702/world_system/world_skill_system/
    # http://localhost:8405/actor/chen_luo/
    # http://localhost:8406/actor/deng_mao/
    # http://localhost:8106/stage/xuzhou_langyaguo_pianyuanshancun_cunkou/

    server_url = "http://localhost:8405/actor/chen_luo/"
    remote: RemoteRunnable[Any, Any] = RemoteRunnable(url=server_url)

    while True:

        try:
            user_input = input("User: ")
            if user_input.lower() in ["quit", "exit", "q"]:
                print("退出！")
                break

            request_data = {
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
