"""Replicate 图片资产生成门面（高层 API）。

语义明确的四个入口：
- ``text_to_image`` / ``batch_text_to_images``：文生图（单个 / 批量）
- ``edit_image`` / ``batch_edit_images``：图生图编辑（单个 / 批量）

单个与批量共用同一"完整请求"类型（:class:`TextToImageJob` / :class:`EditImageJob`），
不含任何隐藏约定：模型、提示词、尺寸等一律显式填写。

另提供通用底层入口 :func:`generate_image_asset`（自定义 ``model_input``）。
低层纯函数见 :mod:`ai_rpg.replicate.pipeline`，并发引擎见 :mod:`ai_rpg.replicate.batch`。
"""

from contextlib import ExitStack
from dataclasses import dataclass
from typing import List, Optional, final

from ..models.image import ImageMeta, ImageSource, new_image_filename
from .batch import batch_generate_images
from .config import replicate_config
from .pipeline import generate_and_download
from .schemas import ReplicateImageInput


################################################################################################################################################################################
@final
@dataclass(frozen=True)
class TextToImageJob:
    """一次文生图的完整输入规格。"""

    model: str
    prompt: str
    negative_prompt: Optional[str] = None
    width: int = 1024
    height: int = 1024
    aspect_ratio: str = "1:1"
    num_inference_steps: int = 4
    guidance_scale: float = 7.5
    seed: Optional[int] = None


################################################################################################################################################################################
@final
@dataclass(frozen=True)
class EditImageJob:
    """一次图生图编辑的完整输入规格。"""

    model: str
    prompt: str
    input_images: List[str]
    output_format: str = "png"
    aspect_ratio: str = "match_input_image"


################################################################################################################################################################################
def _text_to_image_input(job: TextToImageJob) -> ReplicateImageInput:
    """把文生图请求规格转换为 Replicate 模型输入。"""
    model_input: ReplicateImageInput = {
        "prompt": job.prompt,
        "negative_prompt": job.negative_prompt or "",
        "aspect_ratio": job.aspect_ratio,
        "width": job.width,
        "height": job.height,
        "num_outputs": 1,
        "num_inference_steps": job.num_inference_steps,
        "guidance_scale": job.guidance_scale,
        "scheduler": "K_EULER",
        "magic_prompt_option": "Auto",
    }
    if job.seed is not None:
        model_input["seed"] = job.seed
    return model_input


################################################################################################################################################################################
async def generate_image_asset(
    *,
    model: str,
    model_input: ReplicateImageInput,
    source: ImageSource = "text2image",
    input_images: Optional[List[str]] = None,
) -> ImageMeta:
    """通用底层入口：按给定 ``model_input`` 生成并写入 ``.images/<filename>.meta``。

    失败时异常向上抛出；批量场景可配合 ``batch_generate_images`` 隔离。
    常规文生图/图生图请优先使用 :func:`text_to_image` / :func:`edit_image`。
    """
    model_ref = replicate_config.get_model_ref(model)
    ext = str(model_input.get("output_format") or "png")
    meta = ImageMeta.from_generation(
        filename=new_image_filename(ext),
        provider="replicate",
        model=model,
        model_ref=model_ref,
        model_input=dict(model_input),
        source=source,
        input_images=input_images,
    )

    await generate_and_download(model_ref, dict(model_input), str(meta.local_path))
    meta.size_bytes = meta.local_path.stat().st_size
    meta.save()
    return meta


################################################################################################################################################################################
async def text_to_image(*, job: TextToImageJob) -> ImageMeta:
    """文生图：生成一张图片并写入配套 meta。"""
    return await generate_image_asset(
        model=job.model,
        model_input=_text_to_image_input(job),
        source="text2image",
    )


################################################################################################################################################################################
async def edit_image(*, job: EditImageJob) -> ImageMeta:
    """图生图编辑：以 ``job.input_images`` 为输入生成新图片并写入配套 meta。

    负责打开 / 关闭输入文件、拼接模型输入 ``image_input``，并把输入来源
    写入 meta 的 ``input_images``。
    """
    with ExitStack() as stack:
        image_files = [
            stack.enter_context(open(path, "rb")) for path in job.input_images
        ]
        model_input: ReplicateImageInput = {
            "prompt": job.prompt,
            "image_input": image_files,
            "aspect_ratio": job.aspect_ratio,
            "output_format": job.output_format,
        }
        return await generate_image_asset(
            model=job.model,
            model_input=model_input,
            source="image_edit",
            input_images=job.input_images,
        )


################################################################################################################################################################################
async def batch_text_to_images(
    *, jobs: List[TextToImageJob]
) -> List[Optional[ImageMeta]]:
    """批量文生图：并发生成，单个失败不影响其他，失败项为 ``None``。"""
    runner_jobs = [
        (f"text_to_image_{i:02d}", text_to_image(job=job)) for i, job in enumerate(jobs)
    ]
    return await batch_generate_images(runner_jobs)


################################################################################################################################################################################
async def batch_edit_images(*, jobs: List[EditImageJob]) -> List[Optional[ImageMeta]]:
    """批量图生图编辑：并发生成，单个失败不影响其他，失败项为 ``None``。"""
    runner_jobs = [
        (f"edit_image_{i:02d}", edit_image(job=job)) for i, job in enumerate(jobs)
    ]
    return await batch_generate_images(runner_jobs)
