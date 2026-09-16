#!/usr/bin/env python3
"""
Replicate 模块
统一管理 Replicate API 相关功能
"""

from .batch import batch_generate_images
from .client import ReplicateImageRequest
from .config import (
    IMAGES_OUTPUT_DIR,
    IMAGES_URL_PREFIX,
    ReplicateConfig,
    replicate_config,
)
from .connection import check_replicate_connection
from .pipeline import download_image, generate_and_download, generate_image
from .schemas import ReplicateImageInput

__all__ = [
    "ReplicateConfig",
    "ReplicateImageRequest",
    "ReplicateImageInput",
    "check_replicate_connection",
    "generate_image",
    "download_image",
    "generate_and_download",
    "batch_generate_images",
    "replicate_config",
    "IMAGES_OUTPUT_DIR",
    "IMAGES_URL_PREFIX",
]
