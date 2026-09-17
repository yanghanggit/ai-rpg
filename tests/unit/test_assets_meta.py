"""``AssetMeta`` / ``ImageMeta`` 资源资产 meta 协议单元测试。

覆盖：文件名格式与唯一性、路径/URL 派生、provider 必填、``empty`` 兜底、
``save`` / ``load`` 往返、按 ``type`` 判别分发、派生字段不落盘、
``from_generation`` 参数抽取。全部为纯逻辑，不调用任何外部 API。
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

import src.ai_rpg.models.assets_meta as assets_module
from src.ai_rpg.models.assets_meta import (
    ASSETS_DIR,
    ASSETS_URL_PREFIX,
    ASSET_META_SUFFIX,
    AssetKey,
    AssetMeta,
    AssetSource,
    ImageMeta,
    asset_meta_path,
    asset_path,
    asset_url,
    new_asset_filename,
)

# ISO UTC 时间戳 + 32 位 uuid hex
FILENAME_PATTERN = re.compile(r"^\d{8}T\d{6}Z_[0-9a-f]{32}\.png$")


@pytest.fixture
def isolated_assets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把资源资产目录重定向到临时目录，避免污染仓库 .assets/image/。"""
    monkeypatch.setattr(assets_module, "ASSETS_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# 命名与路径协议
# ---------------------------------------------------------------------------


def test_new_asset_filename_format() -> None:
    name = new_asset_filename()
    assert FILENAME_PATTERN.match(name), name


def test_new_asset_filename_unique_and_extension() -> None:
    assert new_asset_filename() != new_asset_filename()
    assert new_asset_filename("webp").endswith(".webp")
    assert new_asset_filename(".jpg").endswith(".jpg")


def test_path_and_url_derivation() -> None:
    name = f"20260916T000000Z_{'a' * 32}.png"
    assert asset_path(name) == ASSETS_DIR / name
    assert asset_url(name) == f"{ASSETS_URL_PREFIX}/{name}"
    assert asset_meta_path(name) == ASSETS_DIR / f"{name}{ASSET_META_SUFFIX}"


def test_asset_key_values() -> None:
    assert AssetKey.COVER.value == "cover"
    assert AssetKey.ILLUSTRATION.value == "illustration"


# ---------------------------------------------------------------------------
# provider 必填 / 空资产兜底
# ---------------------------------------------------------------------------


def test_provider_is_required() -> None:
    with pytest.raises(ValidationError):
        ImageMeta()  # type: ignore[call-arg]


def test_asset_meta_is_abstract_base() -> None:
    assert issubclass(ImageMeta, AssetMeta)
    meta = ImageMeta(provider="replicate")
    assert meta.type == "image"


def test_empty_sentinel() -> None:
    meta = ImageMeta.empty()
    assert meta.provider == ""
    assert meta.filename == ""
    assert meta.is_empty
    assert meta.url == ""
    assert meta.type == "image"


def test_load_empty_value_returns_empty() -> None:
    assert ImageMeta.load("").is_empty


def test_load_missing_meta_falls_back(isolated_assets_dir: Path) -> None:
    meta = ImageMeta.load("does-not-exist.png")
    assert meta.filename == "does-not-exist.png"
    assert meta.provider == ""
    assert not meta.is_empty
    assert meta.url == f"{ASSETS_URL_PREFIX}/does-not-exist.png"


def test_load_accepts_meta_path_and_dispatches(isolated_assets_dir: Path) -> None:
    filename = f"20260916T000000Z_{'c' * 32}.png"
    ImageMeta(provider="replicate", filename=filename).save()

    # 以 meta 路径加载：基类入口按 type 分发到 ImageMeta
    loaded = AssetMeta.load(str(asset_meta_path(filename)))
    assert isinstance(loaded, ImageMeta)
    assert loaded.filename == filename

    # 以 raw filename 加载：同样分发
    loaded_by_name = AssetMeta.load(filename)
    assert isinstance(loaded_by_name, ImageMeta)
    assert loaded_by_name.filename == filename


# ---------------------------------------------------------------------------
# 序列化 / 往返
# ---------------------------------------------------------------------------


def test_url_is_derived_in_dump() -> None:
    meta = ImageMeta(provider="replicate", filename="x.png")
    assert meta.model_dump()["url"] == f"{ASSETS_URL_PREFIX}/x.png"
    assert "url" not in meta.model_dump(exclude={"url"})


def test_save_load_roundtrip(isolated_assets_dir: Path) -> None:
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
    assert saved == isolated_assets_dir / f"{filename}{ASSET_META_SUFFIX}"
    assert saved.exists()

    loaded = ImageMeta.load(filename)
    assert isinstance(loaded, ImageMeta)
    assert loaded.type == "image"
    assert loaded.provider == "replicate"
    assert loaded.filename == filename
    assert loaded.prompt == "a cat"
    assert loaded.model == "nano-banana"
    assert loaded.model_ref == "google/nano-banana"
    assert loaded.width == 1024
    assert loaded.size_bytes == 123
    assert loaded.created_at == meta.created_at
    assert loaded.url == f"{ASSETS_URL_PREFIX}/{filename}"


def test_derived_fields_not_persisted(isolated_assets_dir: Path) -> None:
    meta = ImageMeta(provider="replicate", filename="x.png")
    meta.save()
    raw = (isolated_assets_dir / f"x.png{ASSET_META_SUFFIX}").read_text(
        encoding="utf-8"
    )
    assert '"url"' not in raw
    assert '"local_path"' not in raw
    assert '"meta_path"' not in raw


def test_save_is_atomic_no_tmp_leftover(isolated_assets_dir: Path) -> None:
    ImageMeta(provider="replicate", filename="y.png").save()
    leftovers = list(isolated_assets_dir.glob("*.tmp"))
    assert leftovers == []


# ---------------------------------------------------------------------------
# from_generation
# ---------------------------------------------------------------------------


def test_from_generation_extracts_model_input() -> None:
    meta = ImageMeta.from_generation(
        filename=new_asset_filename(),
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
        source=AssetSource.TEXT2IMAGE,
    )
    assert meta.type == "image"
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
        source=AssetSource.IMAGE_EDIT,
        input_images=["a.png", "b.png"],
    )
    assert meta.format == "webp"
    assert meta.source == "image_edit"
    assert meta.input_images == ["a.png", "b.png"]
