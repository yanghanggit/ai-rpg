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
    POST /api/chat/v1/
"""

import os
import sys

# import asyncio
from typing import Any, Dict

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI
from loguru import logger

from ai_rpg.chat_services.protocol import ChatRequest, ChatResponse
from ai_rpg.azure_openai_gpt import (
    create_chat_workflow,
    execute_chat_workflow,
    create_azure_openai_gpt_llm,
)

from ai_rpg.configuration import (
    server_configuration,
)

##################################################################################################################
# 初始化 FastAPI 应用
app = FastAPI(
    title="Azure OpenAI Chat Server",
    description="基于Azure OpenAI GPT的聊天服务器",
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
        "service": "Azure OpenAI Chat Server",
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "available_endpoints": [
            "GET /",
            "POST /api/chat/v1/",
        ],
        "description": "基于Azure OpenAI的聊天服务器正在正常运行",
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

        # 获取回复 - 直接 await 异步函数
        chat_response = await execute_chat_workflow(
            work_flow=create_chat_workflow(),
            context=[message for message in payload.chat_history],
            request=payload.message,
            llm=create_azure_openai_gpt_llm(),
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
            port=server_configuration.azure_openai_chat_server_port,
            log_level="debug",
        )

    except Exception as e:
        logger.error(f"❌ 启动服务器失败: {e}")
        raise


##################################################################################################################
if __name__ == "__main__":
    main()
