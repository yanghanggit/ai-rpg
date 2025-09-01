#!/usr/bin/env python3
"""
图片生成服务器

功能：
1. 接收文本提示词，使用 Replicate API 生成图片
2. 下载生成的图片到本地
3. 提供静态文件服务，允许客户端访问生成的图片

API 端点：
- GET / : 服务信息
- POST /api/generate : 生成图片
- GET /api/images/list : 获取图片列表
- GET /images/{filename} : 访问静态图片文件

使用示例：
curl http://localhost:{DEFAULT_PORT}/
curl -X POST http://localhost:{DEFAULT_PORT}/api/generate -H "Content-Type: application/json" -d '{"prompt": "a beautiful cat"}'
curl http://localhost:{DEFAULT_PORT}/api/images/list
curl http://localhost:{DEFAULT_PORT}/images/filename.png
"""

import os
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, ConfigDict

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from multi_agents_game.replicate import (
    load_replicate_config,
    generate_and_download,
)

# 全局常量
DEFAULT_PORT = 8300


############################################################################################################
class GenerateImageRequest(BaseModel):
    """图片生成请求模型"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    prompt: str
    model_name: Optional[str] = "sdxl-lightning"
    negative_prompt: Optional[str] = "worst quality, low quality, blurry"
    width: Optional[int] = 768
    height: Optional[int] = 768
    num_inference_steps: Optional[int] = 4
    guidance_scale: Optional[float] = 7.5

请注意 GenerateImageRequest 的参数prompt、negative_prompt、width、height、num_inference_steps 和 guidance_scale，它们共同决定了生成图像的效果。
我希望你做一下分析，找出是否能够一次生成多个图像的方案？

############################################################################################################
class GenerateImageResponse(BaseModel):
    """图片生成响应模型"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool
    message: str
    image_url: Optional[str] = None
    local_path: Optional[str] = None
    filename: Optional[str] = None


############################################################################################################
class ImageListResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    images: List[str]
    total_count: int
    base_url: str


##################################################################################################################
# 加载配置
replicate_config = load_replicate_config(Path("replicate_models.json"))
MODELS = replicate_config.image_models.model_dump(by_alias=True, exclude_none=True)

# 初始化 FastAPI 应用
app = FastAPI(
    title="图片生成服务",
    description="基于 Replicate API 的图片生成和服务",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取项目根目录和图片目录路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
IMAGES_DIR = os.path.join(PROJECT_ROOT, "generated_images")

# 挂载静态文件服务
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


##################################################################################################################
@app.get("/")
async def root() -> Dict[str, Any]:
    """根路径，返回服务信息"""
    return {
        "message": "图片生成服务",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/api/generate",
            "images_list": "/api/images/list",
            "static_images": "/images/{filename}",
            "docs": "/docs",
        },
        "available_models": list(MODELS.keys()),
        "default_params": {
            "model_name": "sdxl-lightning",
            "width": 768,
            "height": 768,
            "num_inference_steps": 4,
            "guidance_scale": 7.5,
        },
    }


##################################################################################################################
@app.post("/api/generate", response_model=GenerateImageResponse)
async def generate_image(request: GenerateImageRequest) -> GenerateImageResponse:
    """生成图片的API端点"""
    try:
        # 确保所有参数都有值（处理 Optional 类型）
        model_name = request.model_name or "sdxl-lightning"
        negative_prompt = (
            request.negative_prompt or "worst quality, low quality, blurry"
        )
        width = request.width or 768
        height = request.height or 768
        num_inference_steps = request.num_inference_steps or 4
        guidance_scale = request.guidance_scale or 7.5

        # 验证模型是否支持
        if model_name not in MODELS:
            available_models = list(MODELS.keys())
            raise HTTPException(
                status_code=400,
                detail=f"不支持的模型: {model_name}. 可用模型: {available_models}",
            )

        logger.info(f"🎨 收到图片生成请求: {request.prompt}")
        logger.info(f"📐 参数: {width}x{height}, 模型: {model_name}")

        # 使用 image_tools 中的 generate_and_download 函数
        saved_path = await generate_and_download(
            prompt=request.prompt,
            model_name=model_name,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            output_dir=IMAGES_DIR,
            models_config=MODELS,
        )

        # 提取文件名
        filename = os.path.basename(saved_path)

        # 构建访问URL
        image_url = f"http://localhost:{DEFAULT_PORT}/images/{filename}"

        logger.info(f"✅ 图片生成成功: {filename}")

        return GenerateImageResponse(
            success=True,
            message="图片生成成功",
            image_url=image_url,
            local_path=saved_path,
            filename=filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 图片生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


##################################################################################################################
@app.get("/api/images/list", response_model=ImageListResponse)
async def list_images() -> ImageListResponse:
    """获取所有可用图片的列表"""
    try:
        if not os.path.exists(IMAGES_DIR):
            raise HTTPException(status_code=404, detail="图片目录不存在")

        # 获取所有图片文件
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
        image_files = []

        for filename in os.listdir(IMAGES_DIR):
            if os.path.isfile(os.path.join(IMAGES_DIR, filename)):
                _, ext = os.path.splitext(filename.lower())
                if ext in image_extensions:
                    image_files.append(filename)

        # 按文件名排序
        image_files.sort()

        return ImageListResponse(
            images=image_files,
            total_count=len(image_files),
            base_url=f"http://localhost:{DEFAULT_PORT}/images",
        )

    except Exception as e:
        logger.error(f"获取图片列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取图片列表失败: {str(e)}")


##################################################################################################################
def main() -> None:
    try:
        # 确保图片目录存在
        os.makedirs(IMAGES_DIR, exist_ok=True)
        logger.info(f"📁 图片目录: {IMAGES_DIR}")

        # 检查模型配置
        if not MODELS:
            logger.error("❌ 错误: 图像模型配置未正确加载")
            logger.error("💡 请检查 replicate_models.json 文件")
            return

        logger.info(f"🎨 已加载 {len(MODELS)} 个可用模型: {list(MODELS.keys())}")

        import uvicorn

        logger.info("🚀 启动图片生成服务器...")
        logger.info(f"📡 API文档: http://localhost:{DEFAULT_PORT}/docs")
        logger.info(f"🖼️  静态文件: http://localhost:{DEFAULT_PORT}/images/")

        # 启动服务器
        uvicorn.run(
            app,
            host="localhost",
            port=DEFAULT_PORT,
            log_level="debug",
        )

    except Exception as e:
        logger.error(f"❌ 启动服务器失败: {e}")
        raise


##################################################################################################################
if __name__ == "__main__":
    main()
