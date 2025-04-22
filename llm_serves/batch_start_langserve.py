import sys
from pathlib import Path
from typing import Final, cast, List

from loguru import logger

sys.path.append(str(Path(__file__).resolve().parent.parent))
import threading
from fastapi import FastAPI
from llm_serves.service_config import (
    GEN_CONFIGS_DIR,
    StartupConfiguration,
)
from langchain.schema import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from llm_serves.chat_request_protocol import (
    ChatRequestModel,
    ChatResponseModel,
)
from llm_serves.azure_chat_openai_gpt_4o_graph import (
    create_compiled_stage_graph,
    stream_graph_updates,
    State,
)


############################################################################################################
class ChatExecutor:

    def __init__(self, api: str, compiled_state_graph: CompiledStateGraph) -> None:
        super().__init__()
        self._api: Final[str] = api
        self._compiled_state_graph: Final[CompiledStateGraph] = compiled_state_graph

    ############################################################################################################
    @property
    def post_url(self) -> str:
        return self._api

    ############################################################################################################
    def process_chat_request(self, request: ChatRequestModel) -> ChatResponseModel:

        # 聊天历史
        chat_history_state: State = {
            "messages": [message for message in request.chat_history]
        }

        # 用户输入
        user_input_state: State = {"messages": [HumanMessage(content=request.input)]}

        # 获取回复
        update_messages = stream_graph_updates(
            state_compiled_graph=self._compiled_state_graph,
            chat_history_state=chat_history_state,
            user_input_state=user_input_state,
        )

        # 返回
        if len(update_messages) > 0:
            return ChatResponseModel(
                agent_name=request.agent_name,
                user_name=request.user_name,
                output=cast(str, update_messages[-1].content),
            )
        return ChatResponseModel(
            agent_name=request.agent_name, user_name=request.user_name, output=""
        )


############################################################################################################
def launch_localhost_chat_server(
    app: FastAPI, port: int, chat_executor: ChatExecutor
) -> None:

    @app.post(path=chat_executor.post_url, response_model=ChatResponseModel)
    async def process_chat_request(
        request_data: ChatRequestModel,
    ) -> ChatResponseModel:
        return chat_executor.process_chat_request(request_data)

    # 启动 FastAPI 应用
    import uvicorn

    uvicorn.run(app, host="localhost", port=port)


############################################################################################################
def main(agent_startup_config_file_path: Path) -> None:

    if not agent_startup_config_file_path.exists():
        # 如果文件不存在，打印错误信息并返回
        logger.error(f"配置文件不存在: {agent_startup_config_file_path}")
        return

    try:

        config_file_content = agent_startup_config_file_path.read_text(encoding="utf-8")
        agent_startup_config = StartupConfiguration.model_validate_json(
            config_file_content
        )

        if len(agent_startup_config.service_configurations) == 0:
            print("没有找到配置")
            return

        threads: List[threading.Thread] = []
        for config in agent_startup_config.service_configurations:
            app = FastAPI(
                title=config.fast_api_title,
                version=config.fast_api_version,
                description=config.fast_api_description,
            )

            chat_executor = ChatExecutor(
                api=str(config.api),
                compiled_state_graph=create_compiled_stage_graph(
                    "azure_chat_openai_chatbot_node", config.temperature
                ),
            )

            # 创建线程并传递当前配置的app和port
            thread = threading.Thread(
                target=launch_localhost_chat_server,
                args=(app, config.port, chat_executor),
            )
            thread.daemon = True
            thread.start()
            threads.append(thread)

        # 主线程等待所有子线程完成（实际uvicorn.run会阻塞）
        for thread in threads:
            thread.join()

    except Exception as e:
        print(f"Exception: {e}")

    # 主线程继续执行其他逻辑或挂起
    # while True:
    #     pass  # 保持主线程存活，防止子线程退出


############################################################################################################
if __name__ == "__main__":

    if len(sys.argv) >= 2:
        arguments = sys.argv[1:]  # 获取除脚本名称外的所有参数
        print("接收到的参数:", arguments)
        main(Path(str(arguments[0])))
    else:
        startup_config_file_path: Path = GEN_CONFIGS_DIR / "start_llm_serves.json"
        assert (
            startup_config_file_path.exists()
        ), f"找不到配置文件: {startup_config_file_path}"
        main(startup_config_file_path)
