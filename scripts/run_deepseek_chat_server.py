#!/usr/bin/env python3
"""
DeepSeek Chat Server启动脚本

功能：
1. 初始化并配置FastAPI应用
2. 注册DeepSeek聊天服务路由
3. 提供动态API信息和健康检查
4. 启动HTTP服务器

架构说明：
- 本文件负责应用配置和启动（表现层）
- 具体的聊天端点实现位于 ai_rpg.services.deepseek_chat 模块
- 采用模块化设计，便于维护和扩展

使用方法：
    python scripts/run_deepseek_chat_server.py

或者在项目根目录下：
    python -m scripts.run_deepseek_chat_server

API端点：
    GET  /                       - API信息和健康检查（动态获取所有路由）
    POST /api/chat/v1/           - 标准聊天（chat模型）
    POST /api/chat/reasoner/v1/  - 推理聊天（reasoner模型）
"""

import os
import sys


# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from typing import Any, Dict
from fastapi import FastAPI, Request
from loguru import logger

from ai_rpg.services import (
    server_configuration,
)
from ai_rpg.services.deepseek_chat import deepseek_chat_api_router

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

############################################################################################################
# 注册路由
app.include_router(deepseek_chat_api_router)


##################################################################################################################
@app.get("/")
async def get_api_info(request: Request) -> Dict[str, Any]:
    """API 根路由接口

    提供 API 服务的基本信息和所有可用端点的列表。

    Args:
        request: FastAPI 请求对象

    Returns:
        Dict[str, Any]: 包含服务信息、状态、可用端点列表和已注册路由的响应字典
    """
    from datetime import datetime
    from fastapi.routing import APIRoute

    base_url = str(request.base_url)
    logger.info(f"获取API路由信息: {base_url}")

    # 收集所有已注册的路由信息
    routes_info = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes_info.append(
                {
                    "path": route.path,
                    "name": route.name,
                    "methods": list(route.methods),
                    "tags": route.tags if route.tags else [],
                }
            )

    return {
        "service": "DeepSeek Chat Server",
        "base_url": base_url,
        "description": "基于DeepSeek的聊天服务器",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "routes": routes_info,
    }


##################################################################################################################
def main() -> None:
    """
    DeepSeek聊天服务器主函数

    功能：
    1. 从配置中读取服务器参数
    2. 启动Uvicorn服务器
    3. 监听并处理HTTP请求

    服务器配置：
    - Host: localhost（仅本地访问）
    - Port: 从 server_configuration.deepseek_chat_server_port 读取
    - Log Level: debug（详细日志）
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
