#!/usr/bin/env python3
"""Replicate 图片生成服务器"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from typing import Any, Dict
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from ai_rpg.replicate import (
    replicate_config,
    DEFAULT_OUTPUT_DIR,
)
from ai_rpg.configuration import server_configuration
from ai_rpg.services.replicate_image import replicate_image_api_router


############################################################################################################
# 初始化 FastAPI 应用
app = FastAPI(
    title="图片生成服务",
    description="基于 Replicate API 的图片生成和服务",
    version="1.0.0",
)
############################################################################################################
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
############################################################################################################
# 挂载静态文件服务
app.mount("/images", StaticFiles(directory=str(DEFAULT_OUTPUT_DIR)), name="images")
############################################################################################################
# 注册路由
app.include_router(replicate_image_api_router)


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
        "service": "Replicate Image Generation Service",
        "base_url": base_url,
        "description": "基于 Replicate API 的图片生成和服务",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "available_models": list(replicate_config.get_available_models().keys()),
        "routes": routes_info,
    }


##################################################################################################################
def main() -> None:

    try:

        import uvicorn

        logger.info("🚀 启动图片生成服务器...")
        logger.info(
            f"📡 API文档: http://localhost:{server_configuration.image_generation_server_port}/docs"
        )
        logger.info(
            f"🖼️  静态文件: http://localhost:{server_configuration.image_generation_server_port}/images/"
        )
        logger.info(
            f"🌐 局域网访问: http://局域网地址:{server_configuration.image_generation_server_port}"
        )

        # 启动服务器
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=server_configuration.image_generation_server_port,
            log_level="debug",
        )

    except Exception as e:
        logger.error(f"❌ 启动服务器失败: {e}")
        raise


##################################################################################################################
if __name__ == "__main__":
    main()
