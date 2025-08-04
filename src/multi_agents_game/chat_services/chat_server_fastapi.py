import sys
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parent.parent))
from fastapi import FastAPI
from langgraph.graph.state import CompiledStateGraph
from ..config import DEFAULT_SERVER_SETTINGS_CONFIG
from ..chat_services.chat_api import ChatRequest, ChatResponse
from ..chat_services.chat_azure_openai_gpt_4o_graph import (
    create_compiled_stage_graph,
    stream_graph_updates,
    State,
)

##################################################################################################################
# 初始化 FastAPI 应用
app = FastAPI()
##################################################################################################################
# 创建编译后的状态图
compiled_state_graph: CompiledStateGraph[State, Any, State, State] = (
    create_compiled_stage_graph("azure_chat_openai_chatbot_node", 0.7)
)


##################################################################################################################
# 定义 POST 请求处理逻辑
@app.post(
    path=DEFAULT_SERVER_SETTINGS_CONFIG.chat_service_endpoint,
    response_model=ChatResponse,
)
async def process_chat_request(request: ChatRequest) -> ChatResponse:
    # 聊天历史
    chat_history_state: State = {
        "messages": [message for message in request.chat_history]
    }

    # 用户输入
    user_input_state: State = {"messages": [request.message]}

    # 获取回复
    update_messages = stream_graph_updates(
        state_compiled_graph=compiled_state_graph,
        chat_history_state=chat_history_state,
        user_input_state=user_input_state,
    )

    # 返回
    return ChatResponse(messages=update_messages)


##################################################################################################################
