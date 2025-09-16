#!/usr/bin/env python3
"""
DeepSeek Chat Server启动脚本

功能：
1. 基于FastAPI构建的DeepSeek聊天服务器
2. 提供RESTful API接口
3. 支持聊天历史和上下文记忆
4. 异步处理聊天请求

使用方法：
    python scripts/run_deepseek_chat_server.py

或者在项目根目录下：
    python -m scripts.run_deepseek_chat_server

API端点：
    GET  /                    - 健康检查
    POST /api/chat/v1/        - 标准聊天
    POST /api/chat/rag/v1/    - RAG聊天
    POST /api/chat/undefined/v1/ - 未定义类型聊天
    POST /api/chat/mcp/v1/    - MCP聊天
"""

import os
from pathlib import Path
import sys
import asyncio
from typing import Any, Dict

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI
from loguru import logger

from multi_agents_game.chat_services.protocol import ChatRequest, ChatResponse
from multi_agents_game.deepseek import (
    State,
    create_compiled_stage_graph,
    stream_graph_updates,
    create_deepseek_llm,
)

from multi_agents_game.settings import (
    initialize_server_settings_instance,
)

##################################################################################################################
# 初始化 FastAPI 应用
app = FastAPI(
    title="DeepSeek Chat Server",
    description="基于DeepSeek的聊天服务器",
    version="1.0.0",
)


##################################################################################################################
# 健康检查端点
@app.get("/")
async def health_check() -> Dict[str, Any]:
    """
    服务器健康检查端点

    Returns:
        dict: 包含服务器状态信息的字典
    """
    from datetime import datetime

    return {
        "service": "DeepSeek Chat Server",
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "available_endpoints": [
            "GET /",
            "POST /api/chat/v1/",
            "POST /api/chat/rag/v1/",
            "POST /api/chat/undefined/v1/",
            "POST /api/chat/mcp/v1/",
        ],
        "description": "基于DeepSeek的聊天服务器正在正常运行",
    }


##################################################################################################################
# 定义 POST 请求处理逻辑
@app.post(
    path="/api/chat/v1/",
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
        llm = create_deepseek_llm()

        # 为每个请求创建独立的状态图实例
        compiled_state_graph = create_compiled_stage_graph("deepseek_chatbot_node")

        # 聊天历史（包含LLM实例）
        chat_history_state: State = {
            "messages": [message for message in request.chat_history],
            "llm": llm,
        }

        # 用户输入
        user_input_state: State = {"messages": [request.message], "llm": llm}

        # 获取回复 - 使用 asyncio.to_thread 将阻塞调用包装为异步
        update_messages = await asyncio.to_thread(
            stream_graph_updates,
            state_compiled_graph=compiled_state_graph,
            chat_history_state=chat_history_state,
            user_input_state=user_input_state,
        )

        logger.success(f"生成回复消息数量: {len(update_messages)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(update_messages):
            logger.success(f"消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=update_messages)

    except Exception as e:
        logger.error(f"处理聊天请求时发生错误: {e}")
        # 返回错误消息
        from langchain.schema import AIMessage

        error_message = AIMessage(content=f"抱歉，处理您的请求时发生错误: {str(e)}")
        return ChatResponse(messages=[error_message])


##################################################################################################################
@app.post(
    path="/api/chat/rag/v1/",
    response_model=ChatResponse,
)
async def process_chat_rag_request(request: ChatRequest) -> ChatResponse:
    """
    处理RAG聊天请求

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    # TODO: 实现RAG聊天逻辑
    return ChatResponse(messages=[])


##################################################################################################################
@app.post(
    path="/api/chat/undefined/v1/",
    response_model=ChatResponse,
)
async def process_chat_undefined_request(request: ChatRequest) -> ChatResponse:
    """
    处理未定义类型的聊天请求

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    # TODO: 实现未定义类型聊天逻辑
    return ChatResponse(messages=[])


##################################################################################################################
@app.post(
    path="/api/chat/mcp/v1/",
    response_model=ChatResponse,
)
async def process_chat_mcp_request(request: ChatRequest) -> ChatResponse:
    """
    处理MCP聊天请求

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    # TODO: 实现MCP聊天逻辑
    return ChatResponse(messages=[])


##################################################################################################################
def main() -> None:
    """
    DeepSeek聊天服务器主函数

    功能：
    1. 启动FastAPI服务器
    2. 配置服务器参数
    3. 提供聊天API服务
    """
    logger.info("🚀 启动DeepSeek聊天服务器...")

    # 加载服务器配置
    server_config = initialize_server_settings_instance(Path("server_settings.json"))

    try:
        import uvicorn

        # 启动服务器
        uvicorn.run(
            app,
            host="localhost",
            port=server_config.deepseek_chat_server_port,
            log_level="debug",
        )

    except Exception as e:
        logger.error(f"❌ 启动服务器失败: {e}")
        raise


##################################################################################################################
if __name__ == "__main__":
    main()
