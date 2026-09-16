#!/usr/bin/env python3
"""
Replicate 图像生成/下载流水线。

以纯函数封装底层 Replicate 调用：
- generate_image: 调用 Replicate 生成图片，返回远端 URL
- image_format_from_url: 从远端 URL 推断图片实际格式
- download_image: 下载远端图片到本地，返回本地路径

异常不在此层捕获，由调用方（如 batch 边界）统一处理。
"""

import time
from pathlib import Path
from typing import Any, Dict, Final, Optional, Set
from urllib.parse import urlparse

import aiohttp
import replicate
from loguru import logger

# 可识别的图片格式（扩展名）
_IMAGE_FORMATS: Final[Set[str]] = {"png", "jpg", "jpeg", "webp"}


################################################################################################################################################################################
def image_format_from_url(image_url: str) -> Optional[str]:
    """从远端图片 URL 推断图片格式（小写扩展名）；无法识别时返回 None。

    Replicate 的产物 URL 以真实格式结尾（如 ``.jpeg`` / ``.png`` / ``.webp``），
    据此命名文件可避免“扩展名与字节内容不符”的问题。
    """
    suffix = Path(urlparse(image_url).path).suffix.lstrip(".").lower()
    return suffix if suffix in _IMAGE_FORMATS else None


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
