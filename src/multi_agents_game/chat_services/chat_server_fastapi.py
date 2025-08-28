from fastapi import FastAPI

from ..chat_services.chat_api import ChatRequest, ChatResponse
from ..azure_openai_gpt import (
    State,
    create_compiled_stage_graph,
    stream_graph_updates,
    create_azure_openai_gpt_llm,
)
from ..config import DEFAULT_SERVER_SETTINGS_CONFIG

##################################################################################################################
# 初始化 FastAPI 应用
app = FastAPI()


##################################################################################################################
# 定义 POST 请求处理逻辑
@app.post(
    path=DEFAULT_SERVER_SETTINGS_CONFIG.chat_service_endpoint,
    response_model=ChatResponse,
)
async def process_chat_request(request: ChatRequest) -> ChatResponse:
    # 为每个请求创建独立的LLM实例
    llm = create_azure_openai_gpt_llm()

    # 为每个请求创建独立的状态图实例
    compiled_state_graph = create_compiled_stage_graph("azure_chat_openai_chatbot_node")

    # 聊天历史（包含LLM实例）
    chat_history_state: State = {
        "messages": [message for message in request.chat_history],
        "llm": llm,
    }

    # 用户输入
    user_input_state: State = {"messages": [request.message], "llm": llm}

    # 获取回复
    update_messages = stream_graph_updates(
        state_compiled_graph=compiled_state_graph,
        chat_history_state=chat_history_state,
        user_input_state=user_input_state,
    )

    # 返回
    return ChatResponse(messages=update_messages)


##################################################################################################################
