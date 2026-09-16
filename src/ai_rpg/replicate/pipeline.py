#!/usr/bin/env python3
"""
Replicate 图像生成/下载流水线。

以纯函数封装底层 Replicate 调用：
- generate_image: 调用 Replicate 生成图片，返回远端 URL
- download_image: 下载远端图片到本地，返回本地路径
- generate_and_download: 生成并下载到指定路径，目标已存在时跳过

异常不在此层捕获，由调用方（如 batch 边界）统一处理。
"""

import time
from pathlib import Path
from typing import Any, Dict

import aiohttp
import replicate
from loguru import logger


async def generate_image(model_ref: str, model_input: Dict[str, Any]) -> str:
    """调用 Replicate 生成图片，返回远端 URL。"""
    start_time = time.time()
    output = await replicate.async_run(model_ref, input=model_input)

    # 处理 FileOutput 对象和列表
    if isinstance(output, list):
        image_url = str(output[0])
    else:
        image_url = str(output)

    elapsed_time = time.time() - start_time
    logger.info(f"✅ 图片生成完成! 耗时: {elapsed_time:.2f}秒")
    logger.info(f"🔗 图片 URL: {image_url}")
    return image_url


async def download_image(image_url: str, save_path: str) -> str:
    """下载远端图片到本地，返回本地路径。"""
    # 确保保存目录存在
    save_dir = Path(save_path).parent
    save_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"📥 异步下载图片到: {save_path}")
    async with aiohttp.ClientSession() as session:
        async with session.get(str(image_url)) as response:
            response.raise_for_status()
            content = await response.read()

    with open(save_path, "wb") as f:
        f.write(content)

    file_size = len(content) / 1024  # KB
    logger.info(f"✅ 异步下载完成! 文件大小: {file_size:.1f} KB")
    return save_path


async def generate_and_download(
    model_ref: str,
    model_input: Dict[str, Any],
    output_path: str,
) -> str:
    """生成图片并下载到 output_path；目标文件已存在时直接跳过。"""
    output_file = Path(output_path)
    if output_file.exists():
        logger.info(f"⏭️  文件已存在，跳过生成: {output_path}")
        return output_path

    image_url = await generate_image(model_ref, model_input)
    return await download_image(image_url, output_path)
