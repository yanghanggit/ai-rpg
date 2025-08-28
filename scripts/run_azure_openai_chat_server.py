#!/usr/bin/env python3
"""
Azure OpenAI Chat Server启动脚本

功能：
1. 基于FastAPI构建的Azure OpenAI GPT聊天服务器
2. 提供RESTful API接口
3. 支持聊天历史和上下文记忆
4. 异步处理聊天请求

使用方法：
    python scripts/run_azure_openai_chat_server.py

或者在项目根目录下：
    python -m scripts.run_azure_openai_chat_server

API端点：
    POST /chat-service/v1/
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI
from loguru import logger

from multi_agents_game.chat_services.chat_api import ChatRequest, ChatResponse
from multi_agents_game.azure_openai_gpt import (
    State,
    create_compiled_stage_graph,
    stream_graph_updates,
    create_azure_openai_gpt_llm,
)

##################################################################################################################
# 初始化 FastAPI 应用
app = FastAPI(
    title="Azure OpenAI Chat Server",
    description="基于Azure OpenAI GPT的聊天服务器",
    version="1.0.0",
)


##################################################################################################################
# 定义 POST 请求处理逻辑
@app.post(
    path="/chat-service/v1/",
    response_model=ChatResponse,
)
async def process_chat_request(request: ChatRequest) -> ChatResponse:
    """
    处理聊天请求

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    try:
        logger.info(f"收到聊天请求: {request.message.content}")

        # 为每个请求创建独立的LLM实例
        llm = create_azure_openai_gpt_llm()

        # 为每个请求创建独立的状态图实例
        compiled_state_graph = create_compiled_stage_graph(
            "azure_chat_openai_chatbot_node"
        )

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

        logger.success(f"生成回复消息数量: {len(update_messages)}")

        # 返回
        return ChatResponse(messages=update_messages)

    except Exception as e:
        logger.error(f"处理聊天请求时发生错误: {e}")
        # 返回错误消息
        from langchain.schema import AIMessage

        error_message = AIMessage(content=f"抱歉，处理您的请求时发生错误: {str(e)}")
        return ChatResponse(messages=[error_message])


##################################################################################################################
def main() -> None:
    """
    Azure OpenAI聊天服务器主函数

    功能：
    1. 启动FastAPI服务器
    2. 配置服务器参数
    3. 提供聊天API服务
    """
    logger.info("🚀 启动Azure OpenAI聊天服务器...")

    try:
        import uvicorn

        # 启动服务器
        uvicorn.run(
            app,
            host="localhost",
            port=8100,
            log_level="debug",
        )

    except Exception as e:
        logger.error(f"❌ 启动服务器失败: {e}")
        raise


##################################################################################################################
if __name__ == "__main__":
    main()
