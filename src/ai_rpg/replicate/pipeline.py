#!/usr/bin/env python3
"""
Replicate 图像生成/下载流水线。

以纯函数封装底层 Replicate 调用：
- generate_image: 调用 Replicate 生成图片，返回远端 URL
- image_format_from_url: 从远端 URL 推断图片实际格式
- download_image: 下载远端图片到本地，返回本地路径

异常在此层只记录日志（含 Replicate prediction 溯源），随后原样上抛，由调用方（如 batch 边界）统一处理。
"""

import time
from pathlib import Path
from typing import Any, Dict, Final, Optional, Set
from urllib.parse import urlparse

import aiohttp
import replicate
from loguru import logger
from replicate.exceptions import ModelError, ReplicateError

# 可识别的图片格式（扩展名）
_IMAGE_FORMATS: Final[Set[str]] = {"png", "jpg", "jpeg", "webp"}

# 日志中提示词的截断长度（避免刷屏）
_PROMPT_LOG_LIMIT: Final[int] = 100


################################################################################################################################################################################
def _truncate(text: str, limit: int = _PROMPT_LOG_LIMIT) -> str:
    """压缩空白并截断文本，用于日志。"""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else f"{flat[:limit]}…"


def _log_prediction_failure(prediction: Any, model_ref: str) -> None:
    """把失败 prediction 的溯源信息写入 logger（id / status / error / logs / metrics）。"""
    logger.error(
        f"❌ Replicate 预测失败: model={model_ref} "
        f"prediction_id={prediction.id} status={prediction.status} "
        f"error={prediction.error!r}"
    )
    if prediction.logs:
        logger.error(f"   预测日志:\n{prediction.logs}")
    if prediction.metrics:
        logger.error(f"   预测指标: {prediction.metrics}")


################################################################################################################################################################################
def image_format_from_url(image_url: str) -> Optional[str]:
    """从远端图片 URL 推断图片格式（小写扩展名）；无法识别时返回 None。

    Replicate 的产物 URL 以真实格式结尾（如 ``.jpeg`` / ``.png`` / ``.webp``），
    据此命名文件可避免“扩展名与字节内容不符”的问题。
    """
    suffix = Path(urlparse(image_url).path).suffix.lstrip(".").lower()
    return suffix if suffix in _IMAGE_FORMATS else None


async def generate_image(model_ref: str, model_input: Dict[str, Any]) -> str:
    """调用 Replicate 生成图片，返回远端 URL。

    失败时在抛错前把关键信息写入 logger：

    - ``ModelError``：模型侧预测失败，输出 ``prediction.id/status/error/logs/metrics``；
    - ``ReplicateError``：Replicate API 错误，输出 ``title/status/detail``；
    - 其他异常（如网络超时）：输出异常类型与消息。
    """
    logger.info(
        f"🎬 Replicate 开始生成: model={model_ref}, "
        f"prompt={_truncate(str(model_input.get('prompt') or ''))!r}"
    )

    start_time = time.time()
    try:
        output = await replicate.async_run(model_ref, input=model_input)
    except ModelError as exc:
        _log_prediction_failure(exc.prediction, model_ref)
        raise
    except ReplicateError as exc:
        logger.error(
            f"❌ Replicate API 错误: model={model_ref} "
            f"title={exc.title!r} status={exc.status} detail={exc.detail!r}"
        )
        raise
    except Exception as exc:
        logger.error(
            f"❌ Replicate 调用异常: model={model_ref} " f"{type(exc).__name__}: {exc}"
        )
        raise

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
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(image_url)) as response:
                response.raise_for_status()
                content = await response.read()
    except Exception as exc:
        logger.error(
            f"❌ 图片下载失败: url={image_url} -> {save_path} "
            f"{type(exc).__name__}: {exc}"
        )
        raise

    with open(save_path, "wb") as f:
        f.write(content)

    file_size = len(content) / 1024  # KB
    logger.info(f"✅ 异步下载完成! 文件大小: {file_size:.1f} KB")
    return save_path
