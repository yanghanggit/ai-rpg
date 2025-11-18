#!/usr/bin/env python3
"""
Replicate 图像生成工具模块
包含异步图像生成和下载工具
"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any

import aiohttp
import replicate
from loguru import logger


# def get_default_generation_params() -> Dict[str, Any]:
#     """
#     获取默认的图片生成参数

#     Returns:
#         包含默认参数的字典
#     """
#     return {
#         "model_name": "sdxl-lightning",
#         "negative_prompt": "worst quality, low quality, blurry",
#         "width": 768,
#         "height": 768,
#         "num_inference_steps": 4,
#         "guidance_scale": 7.5,
#     }


def build_model_input(
    model_name: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_inference_steps: int,
    guidance_scale: float,
) -> Dict[str, Any]:
    """
    根据不同模型构建输入参数

    Args:
        model_name: 模型名称
        prompt: 文本提示词
        negative_prompt: 负向提示词
        width: 图片宽度
        height: 图片高度
        num_inference_steps: 推理步数
        guidance_scale: 引导比例

    Returns:
        构建好的输入参数字典

    Raises:
        ValueError: 不支持的模型名称
    """
    # 基础输入参数（大多数模型通用）
    base_input = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "num_outputs": 1,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "scheduler": "K_EULER",
    }

    # 根据不同模型调整参数
    if model_name == "sdxl-lightning":
        # Lightning 模型使用较少的步数
        base_input["num_inference_steps"] = min(4, num_inference_steps)

    elif model_name == "sdxl":
        # SDXL 模型保持默认参数
        pass

    elif model_name == "playground":
        # Playground 模型可能需要特定的调度器
        base_input["scheduler"] = "DPMSolverMultistep"

    elif model_name == "realvis":
        # RealVis 模型的写实风格调整
        pass

    elif model_name == "ideogram-v3-turbo":
        # Ideogram V3 Turbo 可能有不同的参数名称或默认值
        pass

    else:
        # 对于未知模型，使用基础参数并记录警告
        logger.warning(f"⚠️  未知模型 '{model_name}'，使用默认输入参数")

    logger.debug(f"🔧 模型 {model_name} 输入参数: {base_input}")
    return base_input


async def generate_image(
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
    异步生成图片

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

    logger.info(f"🎨 使用模型: {model_name}")
    logger.info(f"📝 提示词: {prompt}")
    logger.info(f"⚙️  参数: {width}x{height}, {num_inference_steps} 步")
    logger.info("🔄 异步生成中...")

    start_time = time.time()

    try:
        # 构建模型特定的输入参数
        model_input = build_model_input(
            model_name=model_name,
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
        )

        # 使用异步版本
        output = await replicate.async_run(model_version, input=model_input)

        # 获取图片 URL
        image_url: str = output[0] if isinstance(output, list) else str(output)

        elapsed_time = time.time() - start_time
        logger.info(f"✅ 异步生成完成! 耗时: {elapsed_time:.2f}秒")
        logger.info(f"🔗 图片 URL: {image_url}")

        return image_url

    except Exception as e:
        logger.error(f"❌ 异步生成失败: {e}")
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
    异步生成并下载图片的便捷方法

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
        filename: 可选的文件名，不包含扩展名。如果为 None，则使用默认命名规则

    Returns:
        保存的文件路径
    """
    # 异步生成图片
    image_url = await generate_image(
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
    final_filename = f"{model_name}_{timestamp}.png"
    save_path = str(Path(output_dir) / final_filename)

    # 异步下载图片
    downloaded_path = await download_image(image_url, save_path)

    return downloaded_path


async def generate_multiple_images(
    prompts: List[str],
    model_name: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_inference_steps: int,
    guidance_scale: float,
    output_dir: str,
    models_config: Dict[str, Dict[str, str]],
) -> List[str]:
    """
    并发生成多张图片

    Args:
        prompts: 提示词列表
        model_name: 模型名称
        negative_prompt: 负向提示词
        width: 图片宽度
        height: 图片高度
        num_inference_steps: 推理步数
        guidance_scale: 引导比例
        output_dir: 输出目录
        models_config: 模型配置字典
        filenames: 可选的文件名列表，不包含扩展名。如果为 None 或长度不匹配，则使用默认命名规则

    Returns:
        保存的文件路径列表
    """
    logger.info(f"🚀 开始并发生成 {len(prompts)} 张图片...")

    # 创建任务列表
    tasks = []
    for i, prompt in enumerate(prompts):
        task = generate_and_download(
            prompt=prompt,
            model_name=model_name,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            output_dir=output_dir,
            models_config=models_config,
        )
        tasks.append(task)

    # 并发执行所有任务
    start_time = time.time()
    try:
        results = await asyncio.gather(*tasks)
        elapsed_time = time.time() - start_time
        logger.info(f"🎉 并发生成完成! 总耗时: {elapsed_time:.2f}秒")
        logger.info(f"📊 平均每张图片: {elapsed_time/len(prompts):.2f}秒")
        return results
    except Exception as e:
        logger.error(f"❌ 并发生成失败: {e}")
        raise
