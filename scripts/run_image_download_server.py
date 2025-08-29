#!/usr/bin/env python3
"""

curl http://localhost:8300/

获取图片列表：
curl http://localhost:8300/api/images/list

# 在浏览器中打开
curl -I http://localhost:8300/images/sdxl_1754547850.png
"""

import os
import sys
from typing import List, Dict, Any

from pydantic import BaseModel, ConfigDict

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from loguru import logger


class DownloadImageRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image_url: str


############################################################################################################
class ImageListResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    images: List[str]
    total_count: int
    base_url: str


##################################################################################################################
# 初始化 FastAPI 应用
app = FastAPI(
    title="下载图片服务",
    description="测试的下载图片服务",
    version="1.0.0",
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
        "message": "图片下载服务",
        "version": "1.0.0",
        "endpoints": {
            "images_list": "/api/images/list",
            "static_images": "/images/{filename}",
            "docs": "/docs",
        },
    }


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
            base_url="http://localhost:8300/images",
        )

    except Exception as e:
        logger.error(f"获取图片列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取图片列表失败: {str(e)}")


##################################################################################################################
def main() -> None:

    try:
        import uvicorn

        # 启动服务器
        uvicorn.run(
            app,
            host="localhost",
            port=8300,
            log_level="debug",
        )

    except Exception as e:
        logger.error(f"❌ 启动服务器失败: {e}")
        raise


##################################################################################################################
if __name__ == "__main__":
    main()
