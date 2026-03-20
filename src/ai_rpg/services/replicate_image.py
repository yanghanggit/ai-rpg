"""Replicate 图片生成服务模块

提供基于 Replicate API 的图片生成接口，支持单张或批量生成。
"""

import os
import time
import uuid
from typing import List, Dict
from pathlib import Path
from fastapi import APIRouter, HTTPException
from loguru import logger
from ..replicate import (
    replicate_config,
    GENERATED_IMAGES_OUTPUT_DIR,
    ReplicateImageTask,
    run_concurrent_tasks,
    ReplicateImageInput,
)
from ..image_client import (
    ImageGenerationRequest,
    GeneratedImage,
    ImageGenerationResponse,
)

###################################################################################################################################################################
replicate_image_api_router = APIRouter()


###################################################################################################################################################################
@replicate_image_api_router.post(
    "/api/generate/v1", response_model=ImageGenerationResponse
)
async def generate_image(payload: ImageGenerationRequest) -> ImageGenerationResponse:
    """生成图片的 API 端点

    支持单张或批量生成图片。

    Args:
        payload: 图片生成请求对象

    Returns:
        ImageGenerationResponse: 包含生成的图片列表和耗时信息

    Raises:
        HTTPException(400): 模型名称无效
    """
    start_time = time.time()

    logger.info(f"🎨 开始生成图片，配置数量: {len(payload.configs)}")

    # 准备任务列表
    tasks: List[ReplicateImageTask] = []
    task_metadata: Dict[str, Dict[str, str]] = {}  # 文件路径 -> {prompt, model} 的映射

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
        output_path = str(GENERATED_IMAGES_OUTPUT_DIR / filename)

        # 记录映射关系
        task_metadata[output_path] = {
            "prompt": config.prompt,
            "model": model_name,
        }

        # 5. 创建任务（使用 ReplicateImageTask）
        task = ReplicateImageTask(
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

    return ImageGenerationResponse(
        images=images,
        elapsed_time=elapsed_time,
    )


###################################################################################################################################################################
@replicate_image_api_router.get("/api/images/list/v1")
async def list_generated_images() -> List[str]:
    """列出已生成的图片文件

    Returns:
        List[str]: 图片文件名列表
    """
    files = os.listdir(GENERATED_IMAGES_OUTPUT_DIR)
    image_files = [
        f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
    ]
    return image_files
