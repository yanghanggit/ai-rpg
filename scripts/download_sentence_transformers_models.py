#!/usr/bin/env python3
"""预下载 SentenceTransformer 模型到 .sentence_transformers/，支持离线使用。

uv run python scripts/download_sentence_transformers_models.py
uv run python scripts/download_sentence_transformers_models.py --model paraphrase-multilingual-MiniLM-L12-v2
"""

import shutil
from pathlib import Path
from typing import Final, Optional, TypedDict, Dict

import click
from loguru import logger


class ModelConfig(TypedDict):
    description: str
    size_mb: int
    languages: list[str]
    use_case: str


# 项目使用的模型配置
MODELS_CONFIG: Final[Dict[str, ModelConfig]] = {
    "all-MiniLM-L6-v2": {
        "description": "通用英文句子嵌入模型 - 快速轻量",
        "size_mb": 23,
        "languages": ["en"],
        "use_case": "英文内容快速编码",
    },
    "paraphrase-multilingual-MiniLM-L12-v2": {
        "description": "多语言释义检测模型 - 支持中文",
        "size_mb": 135,
        "languages": ["zh", "en", "de", "fr", "ja", "ko", "es", "pt", "ru", "ar"],
        "use_case": "多语言内容语义搜索，项目主要模型",
    },
    "all-mpnet-base-v2": {
        "description": "高质量英文句子嵌入模型",
        "size_mb": 438,
        "languages": ["en"],
        "use_case": "高精度英文语义搜索（可选）",
    },
}

# 默认缓存目录
DEFAULT_CACHE_DIR: Final[Path] = Path(".sentence_transformers")
DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
assert (
    DEFAULT_CACHE_DIR.exists() and DEFAULT_CACHE_DIR.is_dir()
), f"缓存目录创建失败: {DEFAULT_CACHE_DIR}"


def download_model(model_name: str, cache_dir: Path) -> None:
    """下载指定模型到缓存目录，若已存在则先删除再重新下载。"""
    if model_name not in MODELS_CONFIG:
        raise click.BadParameter(f"不支持的模型: {model_name}")

    # 删除已存在的模型缓存
    model_cache_path = cache_dir / model_name
    if model_cache_path.exists():
        logger.info(f"删除已存在的模型缓存: {model_cache_path}")
        shutil.rmtree(model_cache_path)

    # 下载模型
    config = MODELS_CONFIG[model_name]
    logger.info(f"开始下载模型: {model_name}（{config['description']}）")
    logger.info(f"预计大小: {config['size_mb']}MB")

    from sentence_transformers import SentenceTransformer

    # 下载模型并保存到指定缓存目录
    model = SentenceTransformer(model_name)
    model_cache_path.mkdir(parents=True, exist_ok=True)
    model.save(str(model_cache_path))

    # 记录下载完成日志
    logger.success(f"✅ 模型 {model_name} 下载完成: {model_cache_path}")


@click.command()
@click.option(
    "--model",
    type=click.Choice(sorted(MODELS_CONFIG.keys())),
    default=None,
    help="下载指定模型；省略则下载全部模型",
)
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="自定义缓存目录（默认 .sentence_transformers/）",
)
def main(model: Optional[str], cache_dir: Optional[Path]) -> None:
    """下载 SentenceTransformer 模型到本地缓存，支持离线使用。"""
    target_dir = cache_dir or DEFAULT_CACHE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"模型缓存目录: {target_dir}")

    model_names = [model] if model is not None else list(MODELS_CONFIG.keys())
    for model_name in model_names:
        download_model(model_name, target_dir)

    logger.success("🎉 全部模型下载完成")


if __name__ == "__main__":
    main()
