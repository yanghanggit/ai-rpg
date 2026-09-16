"""Replicate 图片生成请求模块

提供异步图片生成请求对象，支持单张和批量生成。
核心功能：
- 直接调用 ai_rpg.replicate 封装模块生成图片（无 HTTP 中间层）
- 批量并发生成多张图片
"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Final, List, final

from loguru import logger

from ..models.image import GeneratedImage
from .config import (
    GENERATED_IMAGES_OUTPUT_DIR,
    GENERATED_IMAGES_URL_PREFIX,
    replicate_config,
)
from .schemas import ReplicateImageInput
from .tasks import ReplicateImageTask


################################################################################################################################################################################
@final
class ReplicateImageRequest:
    """Replicate 图片生成请求

    直接调用 ai_rpg.replicate 封装模块生成图片，无需独立 HTTP 图片服务。
    """

    def __init__(
        self,
        label: str,
        prompt: str,
        negative_prompt: str = "worst quality, low quality, blurry",
        width: int = 1024,
        height: int = 1024,
        model: str = "nano-banana",
    ) -> None:
        self._label = label
        assert self._label != "", "request label should not be empty"

        self._prompt: Final[str] = prompt
        assert self._prompt != "", "prompt should not be empty"

        self._negative_prompt: Final[str] = negative_prompt
        self._width: Final[int] = width
        self._height: Final[int] = height
        self._model: Final[str] = model

        self._images: List[GeneratedImage] = []

    ################################################################################################################################################################################
    @property
    def label(self) -> str:
        return self._label

    ################################################################################################################################################################################
    @property
    def prompt(self) -> str:
        return self._prompt

    ################################################################################################################################################################################
    @property
    def images(self) -> List[GeneratedImage]:
        return self._images

    ################################################################################################################################################################################
    def _compute_aspect_ratio(self) -> str:
        if self._width == self._height:
            return "1:1"
        elif self._width > self._height:
            ratio = self._width / self._height
            if abs(ratio - 16 / 9) < 0.1:
                return "16:9"
            elif abs(ratio - 4 / 3) < 0.1:
                return "4:3"
            else:
                return "1:1"
        else:
            ratio = self._height / self._width
            if abs(ratio - 16 / 9) < 0.1:
                return "9:16"
            elif abs(ratio - 4 / 3) < 0.1:
                return "3:4"
            else:
                return "1:1"

    ################################################################################################################################################################################
    async def generate(self) -> None:
        """异步生成图片，结果保存在 images 属性中。"""
        try:
            logger.debug(f"{self._label} generate prompt:\n{self._prompt}")
            start_time = time.time()

            model_ref = replicate_config.get_model_ref(self._model)
            aspect_ratio = self._compute_aspect_ratio()

            model_input: ReplicateImageInput = {
                "prompt": self._prompt,
                "negative_prompt": self._negative_prompt,
                "aspect_ratio": aspect_ratio,
                "width": self._width,
                "height": self._height,
                "num_outputs": 1,
                "num_inference_steps": 4,
                "guidance_scale": 7.5,
                "scheduler": "K_EULER",
                "magic_prompt_option": "Auto",
            }

            filename = f"{self._model}_{uuid.uuid4()}.png"
            output_path = str(GENERATED_IMAGES_OUTPUT_DIR / filename)

            task = ReplicateImageTask(
                model_ref=model_ref,
                model_input=dict(model_input),
                output_path=output_path,
            )
            local_path = await task.execute()

            elapsed_time = time.time() - start_time
            logger.debug(
                f"{self._label} generate completed in {elapsed_time:.2f} seconds, output: {local_path}"
            )
            self._images = [
                GeneratedImage(
                    filename=Path(local_path).name,
                    url=f"{GENERATED_IMAGES_URL_PREFIX}/{Path(local_path).name}",
                    prompt=self._prompt,
                    model=self._model,
                    local_path=local_path,
                )
            ]
            logger.info(f"{self._label} successfully generated image: {local_path}")

        except ValueError as e:
            logger.error(f"{self._label}: invalid model '{self._model}': {e}")
        except Exception as e:
            logger.error(
                f"{self._label}: unexpected async error: {type(e).__name__}: {e}"
            )

    ################################################################################################################################################################################
    @staticmethod
    async def batch_generate(requests: List["ReplicateImageRequest"]) -> None:
        """批量并发生成多张图片，单个失败不影响其他请求。"""
        if not requests:
            return

        start_time = time.time()
        batch_results = await asyncio.gather(
            *[request.generate() for request in requests],
            return_exceptions=True,
        )
        elapsed_time = time.time() - start_time
        logger.debug(
            f"ReplicateImageRequest.batch_generate: {len(requests)} requests, {elapsed_time:.2f} seconds"
        )

        failed_count = 0
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                label = requests[i].label if i < len(requests) else "unknown"
                logger.error(
                    f"Request failed for '{label}': {type(result).__name__}: {result}"
                )
                failed_count += 1

        if failed_count > 0:
            logger.warning(
                f"ReplicateImageRequest.batch_generate: {failed_count}/{len(requests)} requests failed"
            )
        else:
            logger.debug(
                f"ReplicateImageRequest.batch_generate: All {len(requests)} requests completed successfully"
            )

    ################################################################################################################################################################################
