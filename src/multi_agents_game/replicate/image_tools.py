#!/usr/bin/env python3
"""
Replicate 图像生成工具模块
包含纯函数的图像生成和下载工具
"""

import time
import uuid
from pathlib import Path
from typing import Any, Dict

import replicate
import requests
from loguru import logger


def get_default_generation_params() -> Dict[str, Any]:
    """
    获取默认的图片生成参数

    Returns:
        包含默认参数的字典
    """
    return {
        "model_name": "sdxl-lightning",
        "negative_prompt": "worst quality, low quality, blurry",
        "width": 768,
        "height": 768,
        "num_inference_steps": 4,
        "guidance_scale": 7.5,
    }


def generate_image(
    prompt: str,
    model_name: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_inference_steps: int,
    guidance_scale: float,
    models_config: Dict[str, Dict[str, str]],
) -> str:
    """
    生成图片

    Args:
        prompt: 文本提示词
        model_name: 模型名称
        negative_prompt: 负向提示词
        width: 图片宽度
        height: 图片高度
        num_inference_steps: 推理步数
        guidance_scale: 引导比例
        models_config: 模型配置字典

    Returns:
        图片 URL

    Raises:
        ValueError: 不支持的模型名称
        Exception: 图片生成失败
    """
    if model_name not in models_config:
        raise ValueError(
            f"不支持的模型: {model_name}. 可用模型: {list(models_config.keys())}"
        )

    model_info = models_config[model_name]
    model_version = model_info["version"]
    cost_estimate = model_info["cost_estimate"]

    logger.info(f"🎨 使用模型: {model_name}")
    logger.info(f"💰 预估成本: {cost_estimate}")
    logger.info(f"📝 提示词: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    logger.info(f"⚙️  参数: {width}x{height}, {num_inference_steps} 步")
    logger.info("🔄 生成中...")

    start_time = time.time()

    try:
        # 根据不同模型调整参数
        if model_name == "sdxl-lightning":
            # Lightning 模型使用较少的步数
            num_inference_steps = min(4, num_inference_steps)

        output = replicate.run(
            model_version,
            input={
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "width": width,
                "height": height,
                "num_outputs": 1,
                "num_inference_steps": num_inference_steps,
                "guidance_scale": guidance_scale,
                "scheduler": "K_EULER",
            },
        )

        # 获取图片 URL
        image_url: str = output[0] if isinstance(output, list) else str(output)

        elapsed_time = time.time() - start_time
        logger.info(f"✅ 生成完成! 耗时: {elapsed_time:.2f}秒")
        logger.info(f"🔗 图片 URL: {image_url}")

        return image_url

    except Exception as e:
        logger.error(f"❌ 生成失败: {e}")
        raise


def download_image(image_url: str, save_path: str) -> str:
    """
    下载图片

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
        logger.info(f"📥 下载图片到: {save_path}")

        # 下载图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        # 保存图片
        with open(save_path, "wb") as f:
            f.write(response.content)

        file_size = len(response.content) / 1024  # KB
        logger.info(f"✅ 下载完成! 文件大小: {file_size:.1f} KB")

        return save_path

    except Exception as e:
        logger.error(f"❌ 下载失败: {e}")
        raise


def generate_and_download(
    prompt: str,
    model_name: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_inference_steps: int,
    guidance_scale: float,
    output_dir: str,
    models_config: Dict[str, Dict[str, str]],
) -> str:
    """
    生成并下载图片的便捷方法

    Args:
        prompt: 文本提示词
        model_name: 模型名称
        negative_prompt: 负向提示词
        width: 图片宽度
        height: 图片高度
        num_inference_steps: 推理步数
        guidance_scale: 引导比例
        output_dir: 输出目录
        models_config: 模型配置字典

    Returns:
        保存的文件路径
    """
    # 生成图片
    image_url = generate_image(
        prompt=prompt,
        model_name=model_name,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        models_config=models_config,
    )

    # 准备保存路径
    timestamp = str(uuid.uuid4())
    filename = f"{model_name}_{timestamp}.png"
    save_path = Path(output_dir) / filename

    # 下载图片
    downloaded_path = download_image(image_url, str(save_path))

    return downloaded_path
