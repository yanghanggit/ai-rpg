import sys
from pathlib import Path
import threading

sys.path.append(str(Path(__file__).resolve().parent.parent))
from fastapi import FastAPI
from langserve import (
    add_routes,
)
from llm_serves.service_config import (
    StartupConfiguration,
)
from llm_serves.azure_chat_openai_gpt_4o_graph import (
    create_compiled_stage_graph,
    ChatExecutor,
)


############################################################################################################
def main() -> None:

    if len(sys.argv) < 2:
        print("请提供配置文件路径作为参数")
        sys.exit(1)

    arguments = sys.argv[1:]  # 获取除脚本名称外的所有参数
    print("接收到的参数:", arguments)

    # 读取配置文件
    agent_startup_config_file_path: Path = Path(str(arguments[0]))

    if not agent_startup_config_file_path.exists():
        # 如果文件不存在，打印错误信息并返回
        return

    try:

        config_file_content = agent_startup_config_file_path.read_text(encoding="utf-8")
        agent_startup_config = StartupConfiguration.model_validate_json(
            config_file_content
        )

        if len(agent_startup_config.service_configurations) == 0:
            print("没有找到配置")
            return

        for configuration in agent_startup_config.service_configurations:

            app = FastAPI(
                title=configuration.fast_api_title,
                version=configuration.fast_api_version,
                description=configuration.fast_api_description,
            )

            # 如果api以/结尾，就将尾部的/去掉，不然add_routes会出错.
            api = str(configuration.api)
            if api.endswith("/"):
                api = api[:-1]

            add_routes(
                app,
                ChatExecutor(
                    compiled_state_graph=create_compiled_stage_graph(
                        "azure_chat_openai_chatbot_node", configuration.temperature
                    )
                ),
                path=api,
            )

            # 这么写就是堵塞的。uvicorn.run(app, host="localhost", port=configuration.port)
            def run_server() -> None:
                # 必须这么写。
                import uvicorn

                uvicorn.run(
                    app,
                    host="localhost",
                    port=configuration.port,
                    # 可选：关闭不必要的日志输出
                    # access_log=False,
                )

            # 创建并启动线程
            thread = threading.Thread(target=run_server)
            thread.daemon = True  # 设置为守护线程，主线程退出时自动终止
            thread.start()

    except Exception as e:
        print(f"Exception: {e}")

    # 主线程继续执行其他逻辑或挂起
    while True:
        pass  # 保持主线程存活，防止子线程退出


############################################################################################################
if __name__ == "__main__":
    main()
