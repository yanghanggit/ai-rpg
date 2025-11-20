#!/usr/bin/env python3
""" """

import os
import sys
import time
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field


# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from ai_rpg.replicate import (
    replicate_config,
    DEFAULT_OUTPUT_DIR,
    ImageGenerationAndDownloadTask,
    run_concurrent_tasks,
    ReplicateImageInput,
)
from ai_rpg.configuration import server_configuration

# 局域网地址配置（根据实际情况修改）
# LOCAL_NETWORK_IP = "192.168.192.59"


# ############################################################################################################
class SingleImageGenerationConfig(BaseModel):
    """单张图片生成配置 - 对应一个完整的生成任务"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 必需参数
    prompt: str = Field(..., description="文本提示词")

    # 模型选择
    model: Optional[str] = Field(
        None, description=f"模型名称，默认使用 {replicate_config.default_image_model}"
    )

    # 通用参数
    negative_prompt: str = Field(
        default="worst quality, low quality, blurry", description="负向提示词"
    )
    num_outputs: int = Field(
        default=1, ge=1, le=4, description="每个提示词生成的图片数量"
    )
    num_inference_steps: int = Field(default=4, ge=1, le=50, description="推理步数")
    guidance_scale: float = Field(default=7.5, ge=1.0, le=20.0, description="引导比例")

    # 尺寸参数
    width: int = Field(default=1024, ge=256, le=2048, description="图片宽度")
    height: int = Field(default=1024, ge=256, le=2048, description="图片高度")
    aspect_ratio: Optional[str] = Field(
        None, description="宽高比 (如 '1:1', '16:9')，优先级高于 width/height"
    )

    # 其他可选参数
    scheduler: str = Field(default="K_EULER", description="调度器")
    seed: Optional[int] = Field(None, description="随机种子，用于复现")
    magic_prompt_option: str = Field(
        default="Auto", description="ideogram 专用: Auto/On/Off"
    )


############################################################################################################
class GenerateImagesRequest(BaseModel):
    """图片生成请求模型 - 支持单张或批量生成（每个配置独立）"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 多个独立的生成配置
    configs: List[SingleImageGenerationConfig] = Field(
        ..., description="图片生成配置列表，每个配置独立生成", min_length=1
    )


############################################################################################################
class GeneratedImage(BaseModel):
    """单张生成图片信息"""

    filename: str = Field(..., description="文件名")
    url: str = Field(..., description="访问 URL (相对路径)")
    prompt: str = Field(..., description="使用的提示词")
    model: str = Field(..., description="使用的模型")
    local_path: str = Field(..., description="本地存储路径")


############################################################################################################
class GenerateImagesResponse(BaseModel):
    """图片生成响应模型 - 支持单张或批量响应"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    images: List[GeneratedImage] = Field(
        default_factory=list, description="生成的图片列表"
    )
    elapsed_time: float = Field(..., description="总耗时(秒)")


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
# 图片目录（直接使用 DEFAULT_OUTPUT_DIR）
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"📁 图片目录: {DEFAULT_OUTPUT_DIR}")
############################################################################################################
# 挂载静态文件服务
app.mount("/images", StaticFiles(directory=str(DEFAULT_OUTPUT_DIR)), name="images")


##################################################################################################################
@app.get("/")
async def root() -> Dict[str, Any]:
    """根路径，返回服务信息"""
    return {
        "message": "图片生成服务",
        "version": "1.0.0",
        "endpoints": {
            "generate": "/api/generate/v1",
            "images_list": "/api/images/list/v1",
            "static_images": "/images/{filename}",
            "docs": "/docs",
        },
        "available_models": list(replicate_config.get_available_models().keys()),
    }


##################################################################################################################
@app.post("/api/generate/v1", response_model=GenerateImagesResponse)
async def generate_image(payload: GenerateImagesRequest) -> GenerateImagesResponse:
    """生成图片的API端点 - 支持单张或批量"""
    start_time = time.time()

    try:
        logger.info(f"🎨 开始生成图片，配置数量: {len(payload.configs)}")

        # 准备任务列表
        tasks: List[ImageGenerationAndDownloadTask] = []
        task_metadata: Dict[str, Dict[str, str]] = (
            {}
        )  # 文件路径 -> {prompt, model} 的映射

        # 遍历每个独立的生成配置
        for config in payload.configs:
            # 1. 获取模型版本
            model_name = config.model or replicate_config.default_image_model
            try:
                model_version = replicate_config.get_model_version(model_name)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            # 2. 计算宽高比（如果未指定）
            aspect_ratio = config.aspect_ratio
            if not aspect_ratio:
                if config.width == config.height:
                    aspect_ratio = "1:1"
                elif config.width > config.height:
                    ratio = config.width / config.height
                    if abs(ratio - 16 / 9) < 0.1:
                        aspect_ratio = "16:9"
                    elif abs(ratio - 4 / 3) < 0.1:
                        aspect_ratio = "4:3"
                    else:
                        aspect_ratio = "1:1"
                else:
                    ratio = config.height / config.width
                    if abs(ratio - 16 / 9) < 0.1:
                        aspect_ratio = "9:16"
                    elif abs(ratio - 4 / 3) < 0.1:
                        aspect_ratio = "3:4"
                    else:
                        aspect_ratio = "1:1"

            # 3. 构建模型输入参数（符合 ReplicateImageInput 类型）
            model_input: ReplicateImageInput = {
                "prompt": config.prompt,
                "negative_prompt": config.negative_prompt,
                "aspect_ratio": aspect_ratio,
                "width": config.width,
                "height": config.height,
                "num_outputs": 1,  # 每次生成一张
                "num_inference_steps": config.num_inference_steps,
                "guidance_scale": config.guidance_scale,
                "scheduler": config.scheduler,
                "magic_prompt_option": config.magic_prompt_option,
            }

            # 添加可选的 seed
            if config.seed is not None:
                model_input["seed"] = config.seed

            # 4. 生成输出文件名
            filename = f"{model_name}_{uuid.uuid4()}.png"
            output_path = str(DEFAULT_OUTPUT_DIR / filename)

            # 记录映射关系
            task_metadata[output_path] = {
                "prompt": config.prompt,
                "model": model_name,
            }

            # 5. 创建任务（使用 ImageGenerationAndDownloadTask）
            task = ImageGenerationAndDownloadTask(
                model_version=model_version,
                model_input=dict(model_input),  # 转为普通字典
                output_path=output_path,
            )
            tasks.append(task)

        # 并发执行任务
        logger.info(f"🚀 开始并发生成 {len(tasks)} 张图片...")
        results = await run_concurrent_tasks(tasks)

        # 构建响应
        images: List[GeneratedImage] = []
        for local_path in results:
            filename = Path(local_path).name
            url = f"/images/{filename}"
            metadata = task_metadata.get(
                local_path, {"prompt": "unknown", "model": "unknown"}
            )

            images.append(
                GeneratedImage(
                    filename=filename,
                    url=url,
                    prompt=metadata["prompt"],
                    model=metadata["model"],
                    local_path=local_path,
                )
            )

        elapsed_time = time.time() - start_time
        logger.info(
            f"✅ 图片生成完成! 总耗时: {elapsed_time:.2f}秒, 平均: {elapsed_time/len(images):.2f}秒/张"
        )

        return GenerateImagesResponse(
            images=images,
            elapsed_time=elapsed_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 图片生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"图片生成失败: {str(e)}")


##################################################################################################################
@app.get("/api/images/list/v1")
async def list_generated_images() -> List[str]:
    """列出已生成的图片文件"""
    try:
        files = os.listdir(DEFAULT_OUTPUT_DIR)
        image_files = [
            f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
        ]
        return image_files
    except Exception as e:
        logger.error(f"❌ 列出图片失败: {e}")
        raise HTTPException(status_code=500, detail="无法列出图片文件")


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
