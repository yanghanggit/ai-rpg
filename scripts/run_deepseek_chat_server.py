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
    GET  /                       - 健康检查
    POST /api/chat/v1/           - 标准聊天（chat模型）
    POST /api/chat/reasoner/v1/  - 推理聊天（reasoner模型）
    POST /api/chat/rag/v1/       - RAG聊天
    POST /api/chat/undefined/v1/ - 未定义类型聊天
    POST /api/chat/mcp/v1/       - MCP聊天
"""

import os
import sys


# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from typing import Any, Dict
from fastapi import FastAPI
from loguru import logger
from ai_rpg.chat_service.protocol import ChatRequest, ChatResponse
from ai_rpg.deepseek import (
    create_chat_workflow,
    execute_chat_workflow,
    create_deepseek_chat,
    create_deepseek_reasoner,
)

from ai_rpg.configuration import (
    server_configuration,
)

from typing import Dict, Any
from contextlib import asynccontextmanager
from typing import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理器（现代化方式）

    在应用启动时执行初始化逻辑，在关闭时执行清理逻辑
    """
    # 启动时执行
    logger.info("🚀 应用启动中...")
    # await _initialize_global_mcp_client()
    logger.success("✅ 应用启动完成")

    yield  # 应用运行期间

    # 关闭时执行（如果需要清理资源）
    logger.info("🔄 应用关闭中...")
    # 这里可以添加清理逻辑，比如关闭数据库连接等
    logger.success("✅ 应用关闭完成")


# 初始化 FastAPI 应用（使用现代化生命周期管理）
app = FastAPI(
    title="DeepSeek Chat Server",
    description="基于DeepSeek的聊天服务器",
    version="1.0.0",
    lifespan=lifespan,
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
        "endpoints": [
            "/",
            "/api/chat/v1/",
            "/api/chat/reasoner/v1/",
        ],
        "description": "基于DeepSeek的聊天服务器正在正常运行",
    }


##################################################################################################################
# 定义 POST 请求处理逻辑
@app.post(
    path="/api/chat/v1/",
    response_model=ChatResponse,
)
async def process_chat_request(payload: ChatRequest) -> ChatResponse:
    """
    处理聊天请求

    Args:
        request: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象
    """
    try:
        logger.info(f"收到聊天请求: {payload.message.content}")

        chat_response = await execute_chat_workflow(
            work_flow=create_chat_workflow(),
            context=[message for message in payload.context],
            request=payload.message,
            llm=create_deepseek_chat(),
        )

        logger.success(f"生成回复消息数量: {len(chat_response)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(chat_response):
            logger.success(f"消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=chat_response)

    except Exception as e:
        logger.error(f"处理聊天请求时发生错误: {e}")

    return ChatResponse(messages=[])


##################################################################################################################
# 推理模型聊天端点
@app.post(
    path="/api/chat/reasoner/v1/",
    response_model=ChatResponse,
)
async def process_chat_reasoner_request(payload: ChatRequest) -> ChatResponse:
    """
    处理聊天请求（使用推理模型）

    特性：
    - 使用 DeepSeek Reasoner 模型（思考模式）
    - 提供推理思考过程（reasoning_content）
    - 适合复杂推理任务
    - 注意：不支持工具调用和结构化输出

    Args:
        payload: 包含聊天历史和用户消息的请求对象

    Returns:
        ChatResponse: 包含AI回复消息的响应对象（包含思考过程）
    """
    try:
        logger.info(f"🧠 收到推理模型聊天请求: {payload.message.content}")

        chat_response = await execute_chat_workflow(
            work_flow=create_chat_workflow(),
            context=[message for message in payload.context],
            request=payload.message,
            llm=create_deepseek_reasoner(),  # 使用推理模型
        )

        logger.success(f"生成回复消息数量: {len(chat_response)}")

        # 打印所有消息的详细内容
        for i, message in enumerate(chat_response):
            logger.success(f"消息 {i+1}: {message.model_dump_json(indent=2)}")

        # 返回
        return ChatResponse(messages=chat_response)

    except Exception as e:
        logger.error(f"处理推理模型聊天请求时发生错误: {e}")
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

    try:
        import uvicorn

        # 启动服务器
        uvicorn.run(
            app,
            host="localhost",
            port=server_configuration.deepseek_chat_server_port,
            log_level="debug",
        )

    except Exception as e:
        logger.error(f"❌ 启动服务器失败: {e}")
        raise


##################################################################################################################
if __name__ == "__main__":
    main()
