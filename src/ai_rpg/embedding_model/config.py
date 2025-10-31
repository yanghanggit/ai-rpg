from pathlib import Path
from typing import Final


SENTENCE_TRANSFORMERS_CACHE: Final[Path] = Path(".cache") / "sentence_transformers"
SENTENCE_TRANSFORMERS_CACHE.mkdir(parents=True, exist_ok=True)
assert (
    SENTENCE_TRANSFORMERS_CACHE.exists()
), f"找不到目录: {SENTENCE_TRANSFORMERS_CACHE}"


def cache_path(model_name: str) -> Path:
    """获取模型的缓存路径"""
    return SENTENCE_TRANSFORMERS_CACHE / model_name


def is_model_cached(model_name: str) -> bool:
    """检查模型是否已缓存"""
    return cache_path(model_name).exists()
