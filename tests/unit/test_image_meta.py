"""``ImageMeta`` 图片资产 meta 协议单元测试。

覆盖：文件名格式与唯一性、路径/URL 派生、provider 必填、``empty`` 兜底、
``save`` / ``load`` 往返、派生字段不落盘、``from_generation`` 参数抽取。
全部为纯逻辑，不调用任何外部 API。
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.ai_rpg.models.image as image_module
from src.ai_rpg.models.image import (
    IMAGE_META_SUFFIX,
    IMAGES_DIR,
    IMAGES_URL_PREFIX,
    ImageMeta,
    image_meta_path,
    image_path,
    image_url,
    new_image_filename,
)

# ISO UTC 时间戳 + 32 位 uuid hex
FILENAME_PATTERN = re.compile(r"^\d{8}T\d{6}Z_[0-9a-f]{32}\.png$")


@pytest.fixture
def isolated_images_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把图片资产目录重定向到临时目录，避免污染仓库 .images/。"""
    monkeypatch.setattr(image_module, "IMAGES_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# 命名与路径协议
# ---------------------------------------------------------------------------


def test_new_image_filename_format() -> None:
    name = new_image_filename()
    assert FILENAME_PATTERN.match(name), name


def test_new_image_filename_unique_and_extension() -> None:
    assert new_image_filename() != new_image_filename()
    assert new_image_filename("webp").endswith(".webp")
    assert new_image_filename(".jpg").endswith(".jpg")


def test_path_and_url_derivation() -> None:
    name = f"20260916T000000Z_{'a' * 32}.png"
    assert image_path(name) == IMAGES_DIR / name
    assert image_url(name) == f"{IMAGES_URL_PREFIX}/{name}"
    assert image_meta_path(name) == IMAGES_DIR / f"{name}{IMAGE_META_SUFFIX}"


# ---------------------------------------------------------------------------
# provider 必填 / 空图兜底
# ---------------------------------------------------------------------------


def test_provider_is_required() -> None:
    with pytest.raises(ValidationError):
        ImageMeta()  # type: ignore[call-arg]


def test_empty_sentinel() -> None:
    meta = ImageMeta.empty()
    assert meta.provider == ""
    assert meta.filename == ""
    assert meta.is_empty
    assert meta.url == ""


def test_load_empty_filename_returns_empty() -> None:
    meta = ImageMeta.load("")
    assert meta.is_empty
    assert meta.provider == ""


def test_load_missing_meta_falls_back(isolated_images_dir: Path) -> None:
    meta = ImageMeta.load("does-not-exist.png")
    assert meta.filename == "does-not-exist.png"
    assert meta.provider == ""
    assert not meta.is_empty
    assert meta.url == f"{IMAGES_URL_PREFIX}/does-not-exist.png"


# ---------------------------------------------------------------------------
# 序列化 / 往返
# ---------------------------------------------------------------------------


def test_url_is_derived_in_dump() -> None:
    meta = ImageMeta(provider="replicate", filename="x.png")
    assert meta.model_dump()["url"] == f"{IMAGES_URL_PREFIX}/x.png"
    assert "url" not in meta.model_dump(exclude={"url"})


def test_save_load_roundtrip(isolated_images_dir: Path) -> None:
    filename = f"20260916T000000Z_{'b' * 32}.png"
    meta = ImageMeta(
        provider="replicate",
        filename=filename,
        prompt="a cat",
        negative_prompt="blurry",
        model="nano-banana",
        model_ref="google/nano-banana",
        width=1024,
        height=1024,
        aspect_ratio="1:1",
        size_bytes=123,
    )

    saved = meta.save()
    assert saved == isolated_images_dir / f"{filename}{IMAGE_META_SUFFIX}"
    assert saved.exists()

    loaded = ImageMeta.load(filename)
    assert loaded.provider == "replicate"
    assert loaded.filename == filename
    assert loaded.prompt == "a cat"
    assert loaded.model == "nano-banana"
    assert loaded.model_ref == "google/nano-banana"
    assert loaded.width == 1024
    assert loaded.size_bytes == 123
    assert loaded.created_at == meta.created_at
    assert loaded.url == f"{IMAGES_URL_PREFIX}/{filename}"


def test_derived_fields_not_persisted(isolated_images_dir: Path) -> None:
    meta = ImageMeta(provider="replicate", filename="x.png")
    meta.save()
    raw = (isolated_images_dir / f"x.png{IMAGE_META_SUFFIX}").read_text(
        encoding="utf-8"
    )
    assert '"url"' not in raw
    assert '"local_path"' not in raw
    assert '"meta_path"' not in raw


def test_save_is_atomic_no_tmp_leftover(isolated_images_dir: Path) -> None:
    ImageMeta(provider="replicate", filename="y.png").save()
    leftovers = list(isolated_images_dir.glob("*.tmp"))
    assert leftovers == []


# ---------------------------------------------------------------------------
# from_generation
# ---------------------------------------------------------------------------


def test_from_generation_extracts_model_input() -> None:
    meta = ImageMeta.from_generation(
        filename=new_image_filename(),
        provider="replicate",
        model="flux-schnell",
        model_ref="black-forest-labs/flux-schnell",
        model_input={
            "prompt": "a dog",
            "negative_prompt": "blurry",
            "width": 512,
            "height": 512,
            "aspect_ratio": "1:1",
            "num_inference_steps": 4,
            "guidance_scale": 7.5,
            "scheduler": "K_EULER",
            "seed": 42,
        },
        source="text2image",
    )
    assert meta.prompt == "a dog"
    assert meta.negative_prompt == "blurry"
    assert meta.width == 512
    assert meta.height == 512
    assert meta.num_inference_steps == 4
    assert meta.guidance_scale == 7.5
    assert meta.scheduler == "K_EULER"
    assert meta.seed == 42
    assert meta.source == "text2image"
    assert meta.format == "png"


def test_from_generation_format_and_source_from_args() -> None:
    meta = ImageMeta.from_generation(
        filename="x.webp",
        provider="replicate",
        model="nano-banana",
        model_ref="google/nano-banana",
        model_input={"prompt": "p"},
        source="image_edit",
        input_images=["a.png", "b.png"],
    )
    assert meta.format == "webp"
    assert meta.source == "image_edit"
    assert meta.input_images == ["a.png", "b.png"]
