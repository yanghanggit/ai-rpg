"""资源资产元数据（meta）模型。

采用"raw 资源 + 同名 .meta 文件"配对的管理方式（借鉴 Unity）：

    .assets/image/20260916T155321Z_<uuid32>.png         # raw 资源（系统固定目录）
    .assets/image/20260916T155321Z_<uuid32>.png.meta    # 元数据（本模块序列化的 JSON）

- ``filename`` 是资产唯一键，生成后不再变更；
- ``.assets/image/`` 是系统固定目录，``local_path`` / ``url`` 可由 ``filename`` 完全推导，
  因此不写入 meta；
- :class:`AssetMeta` 是通用基类，携带判别字段 ``type``（与 ``DungeonRoom.type`` 同构），
  具体资源类型（当前仅 :class:`ImageMeta`）继承基类并下沉专属字段；
- 持有方（``Dungeon`` / ``Stage``）只保存 meta 地址（``assets: Dict[AssetKey, str]``），
  不再内连 :class:`AssetMeta` 对象，使用时按地址 :meth:`AssetMeta.load` 读取。
"""

import os
import uuid
from datetime import datetime, timezone
from enum import StrEnum, unique
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Final,
    List,
    Literal,
    Mapping,
    Optional,
    Union,
    final,
)

from pydantic import BaseModel, Field, TypeAdapter, computed_field

###############################################################################################################################################
# 资源资产目录协议（系统固定）
ASSETS_DIR: Final[Path] = Path(".assets/image")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
assert ASSETS_DIR.exists(), "无法创建资源资产目录"

# 静态文件服务的 HTTP URL 前缀（与 run_game_server.py 的 app.mount 保持一致）
ASSETS_URL_PREFIX: Final[str] = "/assets/image"
assert ASSETS_URL_PREFIX.startswith("/"), "URL 前缀必须以 / 开头"

# meta 文件后缀（Unity 风格：<完整文件名>.meta）
ASSET_META_SUFFIX: Final[str] = ".meta"


###############################################################################################################################################
def new_asset_filename(ext: str = "png") -> str:
    """生成新的资产文件名：``<UTC时间戳>_<uuid32>.<ext>``。

    时间戳在前保证字典序等于创建顺序，uuid 保证同秒并发不冲突。
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex}.{ext.lstrip('.')}"


###############################################################################################################################################
def asset_path(filename: str) -> Path:
    """raw 资源路径。"""
    return ASSETS_DIR / filename


###############################################################################################################################################
def asset_url(filename: str) -> str:
    """静态文件服务访问 URL。"""
    return f"{ASSETS_URL_PREFIX}/{filename}"


###############################################################################################################################################
def asset_meta_path(filename: str) -> Path:
    """meta 文件路径（``<filename>.meta``）。"""
    return ASSETS_DIR / f"{filename}{ASSET_META_SUFFIX}"


###############################################################################################################################################
@final
@unique
class AssetKey(StrEnum):
    """资源角色键：持有方按语义键写入 meta 地址，消费方（如客户端）按键取用。

    服务端只负责"设置完毕"，之后不再依赖具体取值；新增角色只需在此扩展。
    """

    COVER = "cover"  # 副本封面（Dungeon.assets）
    ILLUSTRATION = "illustration"  # 场景插图（Stage.assets）


###############################################################################################################################################
@final
@unique
class AssetSource(StrEnum):
    """资产生成方式：文生图 / 图生图（编辑、融合）。"""

    TEXT2IMAGE = "text2image"
    IMAGE_EDIT = "image_edit"


###############################################################################################################################################
class AssetMeta(BaseModel):
    """资源资产元数据（meta）通用基类，与 .assets/image/ 下同名 raw 文件成对存在。

    仅承载跨资源类型的通用字段（身份 / 来源 / 生成溯源 / 文件）：

    - 身份：``type`` / ``schema_version`` / ``filename`` / ``provider`` / ``source`` / ``created_at``
    - 提示：``prompt`` / ``negative_prompt``
    - 模型：``model`` / ``model_ref``
    - 文件：``format`` / ``size_bytes``

    几何 / 采样等资源类型专属字段由子类下沉承载（见 :class:`ImageMeta`）。
    刻意不记录 provider 专属调参，以保证 meta 结构不绑定任何 provider；
    若需逐参数精确复现，请调用方自行持久化完整 ``model_input``；
    边界调整（新增字段）随 ``schema_version`` 一起评估。
    """

    # ---- 判别字段（子类收窄为各自的 Literal 值）----
    type: str = ""

    # ---- 协议与身份 ----
    schema_version: int = 1
    filename: str = ""  # 唯一键（含扩展名），空表示无资产

    # ---- 来源（provider 由上层显式注入，models 层不预设任何 provider）----
    provider: str  # 必填
    source: AssetSource = AssetSource.TEXT2IMAGE

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ---- 生成溯源 ----
    prompt: str = ""
    negative_prompt: str = ""
    model: str = ""  # 逻辑模型名（如 nano-banana）
    model_ref: str = ""  # provider 侧标识（如 google/nano-banana）

    # ---- 文件 ----
    format: str = "png"
    size_bytes: int = 0

    ########################################################################################################################
    # 派生属性：只由 filename + 固定目录推导，不落盘
    ########################################################################################################################
    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """静态访问 URL（派生，每次 dump 现算，永不失效）。"""
        return asset_url(self.filename) if self.filename else ""

    @property
    def local_path(self) -> Path:
        """raw 资源本地路径（派生）。"""
        return asset_path(self.filename)

    @property
    def meta_path(self) -> Path:
        """meta 文件本地路径（派生）。"""
        return asset_meta_path(self.filename)

    @property
    def is_empty(self) -> bool:
        return not self.filename

    ########################################################################################################################
    # 读写
    ########################################################################################################################
    def save(self) -> Path:
        """原子写入同名 .meta 文件（排除派生字段 url），返回 meta 路径。"""
        path = self.meta_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_text(
            self.model_dump_json(indent=2, exclude={"url"}),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
        return path

    ########################################################################################################################
    @classmethod
    def empty(cls) -> "AssetMeta":
        """空 meta（无资产）。provider 为空字符串：models 层不预设任何 provider。"""
        return cls(provider="")

    ########################################################################################################################
    @classmethod
    def load(cls, value: str) -> "AssetMeta":
        """按 meta 路径（``.assets/image/<name>.meta``）或 raw filename 读取 meta。

        - 空值返回 :meth:`empty`；
        - meta 不存在时返回仅含 filename 的兜底对象（provider 为空）；
        - 存在时按 meta 内 ``type`` 判别分发到具体子类。
        """
        if not value:
            return cls.empty()

        name = Path(value).name
        is_meta_path = name.endswith(ASSET_META_SUFFIX)
        meta_path = Path(value) if is_meta_path else asset_meta_path(name)
        if not meta_path.exists():
            filename = name[: -len(ASSET_META_SUFFIX)] if is_meta_path else name
            return cls(provider="", filename=filename)
        return _load_asset_meta(meta_path.read_text(encoding="utf-8"))

    ########################################################################################################################
    @classmethod
    def from_generation(
        cls,
        *,
        filename: str,
        provider: str,
        model: str,
        model_ref: str,
        model_input: Mapping[str, Any],
    ) -> "AssetMeta":
        """从模型输入参数抽取跨资源类型的通用生成溯源信息，构造 meta。"""
        return cls(
            filename=filename,
            provider=provider,
            prompt=str(model_input.get("prompt") or ""),
            negative_prompt=str(model_input.get("negative_prompt") or ""),
            model=model,
            model_ref=model_ref,
            format=Path(filename).suffix.lstrip(".") or "png",
        )


###############################################################################################################################################
@final
class ImageMeta(AssetMeta):
    """图片资产元数据（meta）：在通用字段之上承载几何 / 采样 / 图生图信息。

    记录范围（跨 provider 的生成溯源）：

    - 通用：见 :class:`AssetMeta`
    - 几何：``width`` / ``height`` / ``aspect_ratio``
    - 采样：``num_inference_steps`` / ``guidance_scale`` / ``scheduler`` / ``seed``
    - 图生图：``input_images``
    """

    type: Literal["image"] = "image"

    # ---- 几何 ----
    width: int = 0
    height: int = 0
    aspect_ratio: str = ""

    # ---- 采样 ----
    num_inference_steps: int = 0
    guidance_scale: float = 0.0
    scheduler: str = ""
    seed: Optional[int] = None

    # ---- 图生图 ----
    input_images: List[str] = Field(default_factory=list)  # 图生图来源 filename

    ########################################################################################################################
    @classmethod
    def from_generation(
        cls,
        *,
        filename: str,
        provider: str,
        model: str,
        model_ref: str,
        model_input: Mapping[str, Any],
        source: AssetSource = AssetSource.TEXT2IMAGE,
        input_images: Optional[List[str]] = None,
    ) -> "ImageMeta":
        """从模型输入参数抽取图片生成溯源信息，构造 meta。

        仅抽取 :class:`ImageMeta` 声明范围内的通用字段；provider 专属参数
        （如 ``magic_prompt_option``）刻意忽略，边界见类 docstring。
        """
        return cls(
            filename=filename,
            provider=provider,
            source=source,
            prompt=str(model_input.get("prompt") or ""),
            negative_prompt=str(model_input.get("negative_prompt") or ""),
            model=model,
            model_ref=model_ref,
            width=int(model_input.get("width") or 0),
            height=int(model_input.get("height") or 0),
            aspect_ratio=str(model_input.get("aspect_ratio") or ""),
            num_inference_steps=int(model_input.get("num_inference_steps") or 0),
            guidance_scale=float(model_input.get("guidance_scale") or 0.0),
            scheduler=str(model_input.get("scheduler") or ""),
            seed=model_input.get("seed"),
            input_images=list(input_images or []),
            format=Path(filename).suffix.lstrip(".") or "png",
        )


###############################################################################################################################################
# 判别联合类型：基于 type 字段进行精确的反序列化。
# 只含具体资源类型：AssetMeta 是抽象基类，"base" 资源不存在，故不进入联合。
AnyAssetMeta = Annotated[
    Union[ImageMeta],
    Field(discriminator="type"),
]

###############################################################################################################################################
_ASSET_META_ADAPTER: Final[TypeAdapter[AssetMeta]] = TypeAdapter(AnyAssetMeta)


def _load_asset_meta(text: str) -> AssetMeta:
    """按 meta JSON 内的 ``type`` 判别分发到具体子类。"""
    return _ASSET_META_ADAPTER.validate_json(text)
