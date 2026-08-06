#!/usr/bin/env python3
"""
SentenceTransformer 模型下载和本地缓存管理脚本

该脚本用于：
1. 预下载项目所需的 SentenceTransformer 模型到本地
2. 管理模型的本地缓存
3. 提供模型加载的统一接口
4. 支持离线使用

使用方法：
    python scripts/download_sentence_transformers_models.py --download-all
    python scripts/download_sentence_transformers_models.py --model paraphrase-multilingual-MiniLM-L12-v2
    python scripts/download_sentence_transformers_models.py --list-models
    python scripts/download_sentence_transformers_models.py --check-cache
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    pass


from loguru import logger


class SentenceTransformerModelManager:
    """SentenceTransformer 模型管理器"""

    # 项目使用的模型配置
    MODELS_CONFIG = {
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

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化模型管理器

        Args:
            cache_dir: 模型缓存目录，默认为项目根目录下的 .cache/sentence_transformers
        """
        self.project_root = Path(__file__).parent.parent

        if cache_dir is None:
            self.cache_dir = self.project_root / ".cache" / "sentence_transformers"
        else:
            self.cache_dir = Path(cache_dir)

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 模型信息缓存文件
        self.models_info_file = self.cache_dir / "models_info.json"

        logger.info(f"模型缓存目录: {self.cache_dir}")

    def download_model(
        self, model_name: str, force_download: bool = False
    ) -> Tuple[bool, str]:
        """
        下载指定模型到本地缓存

        Args:
            model_name: 模型名称
            force_download: 是否强制重新下载

        Returns:
            (success, message): 下载结果和消息
        """
        if model_name not in self.MODELS_CONFIG:
            return False, f"不支持的模型: {model_name}"

        model_cache_path = self.cache_dir / model_name

        # 检查是否已经存在
        if model_cache_path.exists() and not force_download:
            logger.info(f"模型 {model_name} 已存在于缓存中: {model_cache_path}")
            return True, f"模型已存在: {model_cache_path}"

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"开始下载模型: {model_name}")
            logger.info(f"预计大小: {self.MODELS_CONFIG[model_name]['size_mb']}MB")

            # 下载模型（这会自动缓存到 Hugging Face 的默认缓存目录）
            model = SentenceTransformer(model_name)

            # 保存模型到我们的自定义缓存目录
            model_cache_path.mkdir(parents=True, exist_ok=True)
            model.save(str(model_cache_path))

            # 更新模型信息
            self._update_model_info(model_name, model_cache_path)

            logger.info(f"✅ 模型 {model_name} 下载完成: {model_cache_path}")
            return True, f"下载完成: {model_cache_path}"

        except Exception as e:
            logger.error(f"❌ 下载模型 {model_name} 失败: {e}")
            # 清理可能不完整的下载
            if model_cache_path.exists():
                shutil.rmtree(model_cache_path)
            return False, f"下载失败: {e}"

    def list_cached_models(self) -> List[Dict[str, Any]]:
        """列出所有已缓存的模型"""
        cached_models: List[Dict[str, Any]] = []

        if not self.cache_dir.exists():
            return cached_models

        for model_dir in self.cache_dir.iterdir():
            if model_dir.is_dir() and model_dir.name in self.MODELS_CONFIG:
                model_info = self.MODELS_CONFIG[model_dir.name].copy()
                model_info["name"] = model_dir.name
                model_info["cache_path"] = str(model_dir)
                model_info["cached"] = True

                # 计算实际缓存大小
                try:
                    size_bytes = sum(
                        f.stat().st_size for f in model_dir.rglob("*") if f.is_file()
                    )
                    model_info["actual_size_mb"] = round(size_bytes / (1024 * 1024), 2)
                except Exception:
                    model_info["actual_size_mb"] = "未知"

                cached_models.append(model_info)

        return cached_models

    def list_all_models(self) -> List[Dict[str, Any]]:
        """列出所有支持的模型（包括未缓存的）"""
        all_models: List[Dict[str, Any]] = []
        cached_models = {m["name"] for m in self.list_cached_models()}

        for model_name, config in self.MODELS_CONFIG.items():
            model_info = config.copy()
            model_info["name"] = model_name
            model_info["cached"] = model_name in cached_models

            if model_info["cached"]:
                cache_path = self.cache_dir / model_name
                model_info["cache_path"] = str(cache_path)

            all_models.append(model_info)

        return all_models

    def download_all_models(
        self, force_download: bool = False
    ) -> Dict[str, Tuple[bool, str]]:
        """下载所有项目模型"""
        results = {}

        logger.info("🚀 开始下载所有项目模型...")

        for model_name in self.MODELS_CONFIG.keys():
            logger.info(f"\n📦 处理模型: {model_name}")
            success, message = self.download_model(model_name, force_download)
            results[model_name] = (success, message)

        return results

    def clear_cache(self, model_name: Optional[str] = None) -> bool:
        """清理模型缓存"""
        try:
            if model_name:
                # 清理特定模型
                model_path = self.cache_dir / model_name
                if model_path.exists():
                    shutil.rmtree(model_path)
                    logger.info(f"✅ 已清理模型缓存: {model_name}")
                else:
                    logger.info(f"模型缓存不存在: {model_name}")
            else:
                # 清理所有缓存
                if self.cache_dir.exists():
                    shutil.rmtree(self.cache_dir)
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("✅ 已清理所有模型缓存")

            return True

        except Exception as e:
            logger.error(f"❌ 清理缓存失败: {e}")
            return False

    def _update_model_info(self, model_name: str, model_path: Path) -> None:
        """更新模型信息缓存"""
        try:
            # 加载现有信息
            if self.models_info_file.exists():
                with open(self.models_info_file, "r", encoding="utf-8") as f:
                    models_info = json.load(f)
            else:
                models_info = {}

            # 更新模型信息
            models_info[model_name] = {
                "cache_path": str(model_path),
                "downloaded_at": datetime.now().isoformat(),
                "config": self.MODELS_CONFIG.get(model_name, {}),
            }

            # 保存更新后的信息
            with open(self.models_info_file, "w", encoding="utf-8") as f:
                json.dump(models_info, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"更新模型信息失败: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        stats: Dict[str, Any] = {
            "cache_dir": str(self.cache_dir),
            "total_models": len(self.MODELS_CONFIG),
            "cached_models": 0,
            "total_cache_size_mb": 0.0,
            "models": [],
        }

        if not self.cache_dir.exists():
            return stats

        cached_models = self.list_cached_models()
        stats["cached_models"] = len(cached_models)

        total_size: float = 0.0
        models_list: List[Dict[str, Any]] = []

        for model in cached_models:
            actual_size = model.get("actual_size_mb")
            if isinstance(actual_size, (int, float)):
                total_size += actual_size
            models_list.append(model)

        stats["total_cache_size_mb"] = round(total_size, 2)
        stats["models"] = models_list

        return stats


def print_models_table(models: List[Dict[str, Any]]) -> None:
    """打印模型表格"""
    print("\n" + "=" * 120)
    print(f"{'模型名称':<40} {'状态':<8} {'大小(MB)':<10} {'语言':<15} {'用途':<45}")
    print("=" * 120)

    for model in models:
        name = model["name"]
        cached = "✅ 已缓存" if model.get("cached", False) else "❌ 未缓存"
        size = f"{model['size_mb']}"
        languages = ", ".join(model["languages"][:3])  # 显示前3种语言
        if len(model["languages"]) > 3:
            languages += "..."
        use_case = (
            model["use_case"][:40] + "..."
            if len(model["use_case"]) > 40
            else model["use_case"]
        )

        print(f"{name:<40} {cached:<8} {size:<10} {languages:<15} {use_case:<45}")

    print("=" * 120)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SentenceTransformer 模型下载和管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 下载所有项目模型
  python scripts/download_sentence_transformers_models.py --download-all
  
  # 下载特定模型
  python scripts/download_sentence_transformers_models.py --model paraphrase-multilingual-MiniLM-L12-v2
  
  # 查看所有模型状态
  python scripts/download_sentence_transformers_models.py --list-models
  
  # 查看缓存统计
  python scripts/download_sentence_transformers_models.py --check-cache
  
  # 清理所有缓存
  python scripts/download_sentence_transformers_models.py --clear-cache
        """,
    )

    parser.add_argument("--download-all", action="store_true", help="下载所有项目模型")
    parser.add_argument("--model", type=str, help="下载指定模型")
    parser.add_argument("--list-models", action="store_true", help="列出所有支持的模型")
    parser.add_argument("--check-cache", action="store_true", help="检查缓存状态")
    parser.add_argument("--clear-cache", action="store_true", help="清理所有模型缓存")
    parser.add_argument("--force", action="store_true", help="强制重新下载")
    parser.add_argument("--cache-dir", type=str, help="自定义缓存目录")

    args = parser.parse_args()

    # 创建模型管理器
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    manager = SentenceTransformerModelManager(cache_dir)

    if args.download_all:
        print("🚀 开始下载所有项目模型...")
        results = manager.download_all_models(args.force)

        print("\n📊 下载结果汇总:")
        print("=" * 80)
        for model_name, (success, message) in results.items():
            status = "✅ 成功" if success else "❌ 失败"
            print(f"{model_name:<40} {status:<8} {message}")
        print("=" * 80)

    elif args.model:
        print(f"📦 下载模型: {args.model}")
        success, message = manager.download_model(args.model, args.force)
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{status}: {message}")

    elif args.list_models:
        models = manager.list_all_models()
        print("📋 所有支持的模型:")
        print_models_table(models)

    elif args.check_cache:
        stats = manager.get_cache_stats()
        print("📊 缓存统计信息:")
        print("=" * 60)
        print(f"缓存目录: {stats['cache_dir']}")
        print(f"支持模型总数: {stats['total_models']}")
        print(f"已缓存模型数: {stats['cached_models']}")
        print(f"缓存总大小: {stats['total_cache_size_mb']} MB")

        if stats["models"]:
            print("\n已缓存的模型:")
            print_models_table(stats["models"])
        else:
            print("\n❌ 没有已缓存的模型")

    elif args.clear_cache:
        print("🗑️  清理所有模型缓存...")
        if manager.clear_cache():
            print("✅ 缓存清理完成")
        else:
            print("❌ 缓存清理失败")

    else:
        parser.print_help()
        print("\n💡 建议首先运行: --download-all 来下载所有项目模型")


if __name__ == "__main__":
    main()
