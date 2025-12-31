#!/usr/bin/env python3
"""
Replicate 模块类型定义
包含 Replicate API 相关的类型定义
"""

from typing import TypedDict


class ReplicateImageInput(TypedDict, total=False):
    """
    Replicate 图像生成模型通用输入参数 Schema

    不同模型支持不同的参数子集:
    - ideogram-v3-turbo: 使用 aspect_ratio (不支持 width/height)
    - stable-diffusion-3.5-large: 使用 width/height
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
    width: int  # SD 3.5, flux 等模型使用
    height: int  # SD 3.5, flux 等模型使用
    aspect_ratio: str  # ideogram 系列使用 (如 "1:1", "16:9", "9:16")

    # 调度器
    scheduler: str  # 如 "K_EULER", "DDIM" 等

    # 其他可选参数
    seed: int  # 随机种子
    output_format: str  # 输出格式: "webp", "jpg", "png" (SD 3.5, nano-banana 支持)
    output_quality: int  # 输出质量: 0-100 (SD 3.5 支持)
    magic_prompt_option: str  # ideogram 专用: "Auto", "On", "Off"
    resolution: str  # nano-banana-pro 专用: "1K", "2K", "4K"
    safety_filter_level: str  # nano-banana-pro 专用: "block_low_and_above", "block_medium_and_above", "block_only_high"
    image_input: list  # nano-banana 系列: 输入图像列表（用于图像编辑和融合）
