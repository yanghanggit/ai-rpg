#!/usr/bin/env python3
"""
Replicate 图像任务模块
包含异步图像生成任务、下载任务，以及批量并发执行工具
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import replicate
from loguru import logger
from pydantic import BaseModel


class ImageGenerationTask(BaseModel):
    """图像生成任务"""

    model_ref: str
    model_input: Dict[str, Any]

    # 输出结果（None 表示未完成）
    image_url: Optional[str] = None

    async def execute(self) -> str:
        """执行图像生成"""
        start_time = time.time()

        try:
            # 核心调用
            output = await replicate.async_run(self.model_ref, input=self.model_input)

            # 获取图片 URL（处理 FileOutput 对象和列表）
            if isinstance(output, list):
                # 列表情况：取第一个元素并转换为字符串
                self.image_url = str(output[0])
            else:
                # 单个对象：直接转换为字符串
                self.image_url = str(output)

            elapsed_time = time.time() - start_time
            logger.info(f"✅ 图片生成完成! 耗时: {elapsed_time:.2f}秒")
            logger.info(f"🔗 图片 URL: {self.image_url}")

            return self.image_url

        except Exception as e:
            logger.error(f"❌ 图片生成失败: {e}")
            raise


class ImageDownloadTask(BaseModel):
    """图像下载任务"""

    image_url: str
    save_path: str

    # 输出结果（None 表示未完成）
    local_path: Optional[str] = None

    async def execute(self) -> str:
        """执行图像下载"""
        # 确保保存目录存在
        save_dir = Path(self.save_path).parent
        save_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"📥 异步下载图片到: {self.save_path}")

            # 异步下载图片
            async with aiohttp.ClientSession() as session:
                async with session.get(str(self.image_url)) as response:
                    response.raise_for_status()
                    content = await response.read()

            # 保存图片
            with open(self.save_path, "wb") as f:
                f.write(content)

            file_size = len(content) / 1024  # KB
            logger.info(f"✅ 异步下载完成! 文件大小: {file_size:.1f} KB")

            self.local_path = self.save_path
            return self.local_path

        except Exception as e:
            logger.error(f"❌ 异步下载失败: {e}")
            raise


class ReplicateImageTask(BaseModel):
    """
    Replicate 图像处理任务

    通用任务类，支持：
    - 图像生成 (text-to-image)
    - 图像编辑 (image-to-image)
    - 其他 Replicate 图像 API

    执行流程：调用 API → 下载结果
    """

    model_ref: str
    model_input: Dict[str, Any]
    output_path: str

    # 子任务（None 表示未初始化/未执行）
    generation_task: Optional[ImageGenerationTask] = None
    download_task: Optional[ImageDownloadTask] = None

    async def execute(self) -> str:
        """执行完整任务流程"""
        # 检查文件是否已存在
        output_file = Path(self.output_path)
        if output_file.exists():
            logger.info(f"⏭️  文件已存在，跳过生成: {self.output_path}")
            return self.output_path

        # 步骤1: 生成图像
        self.generation_task = ImageGenerationTask(
            model_ref=self.model_ref, model_input=self.model_input
        )
        image_url = await self.generation_task.execute()

        # 步骤2: 下载图像
        self.download_task = ImageDownloadTask(
            image_url=image_url, save_path=self.output_path
        )
        local_path = await self.download_task.execute()

        return local_path


async def generate_images_concurrently(
    tasks: List[ReplicateImageTask],
) -> List[str]:
    """
    并发执行多个图像生成和下载任务

    Args:
        tasks: 任务列表 (ReplicateImageTask)

    Returns:
        保存的文件路径列表
    """
    logger.info(f"🚀 开始并发生成 {len(tasks)} 张图片...")

    start_time = time.time()
    try:
        results = await asyncio.gather(*[task.execute() for task in tasks])
        elapsed_time = time.time() - start_time
        logger.info(f"🎉 并发生成完成! 总耗时: {elapsed_time:.2f}秒")
        logger.info(f"📊 平均每张图片: {elapsed_time/len(tasks):.2f}秒")
        return results
    except Exception as e:
        logger.error(f"❌ 并发生成失败: {e}")
        raise
