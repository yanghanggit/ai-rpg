#!/usr/bin/env python3
"""
Replicate 模块
统一管理 Replicate API 相关功能
"""

from .assets import (
    EditImageJob,
    TextToImageJob,
    batch_edit_images,
    batch_text_to_images,
    edit_image,
    generate_image_asset,
    text_to_image,
)
from .batch import batch_generate_images
from .config import (
    ReplicateConfig,
    replicate_config,
)
from .connection import check_replicate_connection
from .pipeline import download_image, generate_and_download, generate_image
from .schemas import ReplicateImageInput

__all__ = [
    "ReplicateConfig",
    "ReplicateImageInput",
    # 语义化入口（推荐）
    "TextToImageJob",
    "EditImageJob",
    "text_to_image",
    "edit_image",
    "batch_text_to_images",
    "batch_edit_images",
    # 通用底层入口
    "generate_image_asset",
    "check_replicate_connection",
    "generate_image",
    "download_image",
    "generate_and_download",
    "batch_generate_images",
    "replicate_config",
]
