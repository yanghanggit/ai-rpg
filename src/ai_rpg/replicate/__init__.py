#!/usr/bin/env python3
"""
Replicate 模块
统一管理 Replicate API 相关功能

分层（由上到下）：

1. 语义化入口（推荐日常使用）
   ``text_to_image`` / ``edit_image`` / ``batch_text_to_images`` / ``batch_edit_images``
2. 通用底层门面（需要自定义 ``model_input`` 时使用）
   ``generate_image_asset``
3. 传输纯函数（生成 / 下载）
   ``generate_image`` / ``image_format_from_url`` / ``download_image``
4. 并发引擎
   ``batch_generate_images``
5. 配置与连通性
   ``DEFAULT_IMAGE_MODEL`` / ``IMAGE_MODELS`` / ``check_replicate_connection``

低层函数一并导出，便于按需组合；日常调用请优先使用第 1 层。
"""

from .assets import (
    EditImageSpec,
    TextToImageSpec,
    batch_edit_images,
    batch_text_to_images,
    edit_image,
    generate_image_asset,
    text_to_image,
)
from .batch import batch_generate_images
from .config import (
    DEFAULT_IMAGE_MODEL,
    IMAGE_MODELS,
)
from .connection import check_replicate_connection
from .pipeline import (
    download_image,
    generate_image,
    image_format_from_url,
)
from .schemas import ReplicateImageInput

__all__ = [
    "DEFAULT_IMAGE_MODEL",
    "IMAGE_MODELS",
    "ReplicateImageInput",
    # 语义化入口（推荐）
    "TextToImageSpec",
    "EditImageSpec",
    "text_to_image",
    "edit_image",
    "batch_text_to_images",
    "batch_edit_images",
    # 通用底层入口
    "generate_image_asset",
    "check_replicate_connection",
    "generate_image",
    "image_format_from_url",
    "download_image",
    "batch_generate_images",
]
