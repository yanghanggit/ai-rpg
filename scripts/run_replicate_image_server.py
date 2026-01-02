#!/usr/bin/env python3
"""Replicate 图片生成服务器"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from ai_rpg.replicate import (
    replicate_config,
    DEFAULT_OUTPUT_DIR,
)
from ai_rpg.configuration import server_configuration
from ai_rpg.models import (
    ImageRootResponse,
)
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
async def root() -> ImageRootResponse:
    """根路径，返回服务信息"""
    return ImageRootResponse(
        message="图片生成服务",
        version="1.0.0",
        endpoints={
            "generate": "/api/generate/v1",
            "images_list": "/api/images/list/v1",
            "static_images": "/images/{filename}",
            "docs": "/docs",
        },
        available_models=list(replicate_config.get_available_models().keys()),
    )


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
