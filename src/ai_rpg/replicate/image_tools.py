#!/usr/bin/env python3
"""
Replicate 图像生成工具模块
包含异步图像生成和下载工具
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, TypedDict
import aiohttp
import replicate
from loguru import logger


class ReplicateImageInput(TypedDict, total=False):
    """
    Replicate 图像生成模型通用输入参数 Schema

    不同模型支持不同的参数子集:
    - ideogram-v3-turbo: 使用 aspect_ratio (不支持 width/height)
    - flux-schnell: 使用 width/height
    - 其他模型: 根据官方文档选择对应参数

    使用方式: 填充所有可能的参数，模型会自动选择其支持的参数使用
    """

    # 必需参数
    prompt: str

    # 通用参数
    negative_prompt: str
    num_outputs: int
    num_inference_steps: int
    guidance_scale: float

    # 尺寸参数 (不同模型选其一)
    width: int  # 某些模型使用 (如 flux)
    height: int  # 某些模型使用 (如 flux)
    aspect_ratio: str  # ideogram 系列使用 (如 "1:1", "16:9", "9:16")

    # 调度器
    scheduler: str  # 如 "K_EULER", "DDIM" 等

    # 其他可选参数
    seed: int  # 随机种子
    magic_prompt_option: str  # ideogram 专用: "Auto", "On", "Off"


class ImageGenerationTask(NamedTuple):
    """图像生成任务"""

    model_version: str
    model_input: Dict[str, Any]
    output_path: str


async def generate_image(model_version: str, model_input: Dict[str, Any]) -> str:
    """
    异步生成图片 - 核心函数

    Args:
        model_version: 模型版本字符串
        model_input: 模型输入参数字典

    Returns:
        图片 URL

    Raises:
        Exception: 图片生成失败
    """
    start_time = time.time()

    try:
        # 核心调用
        output = await replicate.async_run(model_version, input=model_input)

        # 获取图片 URL
        image_url: str = output[0] if isinstance(output, list) else str(output)

        elapsed_time = time.time() - start_time
        logger.info(f"✅ 图片生成完成! 耗时: {elapsed_time:.2f}秒")
        logger.info(f"🔗 图片 URL: {image_url}")

        return image_url

    except Exception as e:
        logger.error(f"❌ 图片生成失败: {e}")
        raise


async def download_image(image_url: str, save_path: str) -> str:
    """
    异步下载图片

    Args:
        image_url: 图片 URL
        save_path: 保存路径

    Returns:
        保存的文件路径

    Raises:
        Exception: 下载失败
    """
    # 确保保存目录存在
    save_dir = Path(save_path).parent
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        logger.info(f"📥 异步下载图片到: {save_path}")

        # 异步下载图片
        async with aiohttp.ClientSession() as session:
            async with session.get(str(image_url)) as response:
                response.raise_for_status()
                content = await response.read()

        # 保存图片
        with open(save_path, "wb") as f:
            f.write(content)

        file_size = len(content) / 1024  # KB
        logger.info(f"✅ 异步下载完成! 文件大小: {file_size:.1f} KB")

        return save_path

    except Exception as e:
        logger.error(f"❌ 异步下载失败: {e}")
        raise


async def generate_and_download(
    model_version: str,
    model_input: Dict[str, Any],
    output_path: str,
) -> str:
    """
    生成并下载图片

    Args:
        model_version: 模型版本
        model_input: 模型输入参数字典
        output_path: 完整输出路径(包括文件名,如 "outputs/cat_001.png")

    Returns:
        保存的文件路径
    """
    # 生成图片
    image_url = await generate_image(model_version, model_input)

    # 下载图片
    await download_image(image_url, output_path)

    return output_path


async def execute_tasks(
    tasks: List[ImageGenerationTask],
) -> List[str]:
    """
    并发生成多张图片

    Args:
        tasks: 任务列表,每个任务是 ImageGenerationTask

    Returns:
        保存的文件路径列表
    """
    logger.info(f"🚀 开始并发生成 {len(tasks)} 张图片...")

    # 创建协程列表
    coroutines = [
        generate_and_download(task.model_version, task.model_input, task.output_path)
        for task in tasks
    ]

    # 并发执行所有任务
    start_time = time.time()
    try:
        results = await asyncio.gather(*coroutines)
        elapsed_time = time.time() - start_time
        logger.info(f"🎉 并发生成完成! 总耗时: {elapsed_time:.2f}秒")
        logger.info(f"📊 平均每张图片: {elapsed_time/len(tasks):.2f}秒")
        return results
    except Exception as e:
        logger.error(f"❌ 并发生成失败: {e}")
        raise
