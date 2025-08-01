"""
SentenceTransformer 模型加载工具模块

提供统一的模型加载接口，优先使用本地缓存，支持离线使用。
"""

import os
import sys
from pathlib import Path
from typing import Optional, Union, TYPE_CHECKING, Any
import logging

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

# 添加 scripts 路径以便导入模型管理器
project_root = Path(__file__).parent.parent.parent.parent
scripts_path = project_root / "scripts"
if str(scripts_path) not in sys.path:
    sys.path.insert(0, str(scripts_path))

try:
    from download_sentence_transformers_models import SentenceTransformerModelManager
except ImportError:
    # 如果无法导入，创建一个简化版本
    SentenceTransformerModelManager = None

logger = logging.getLogger(__name__)


class ModelLoader:
    """统一的模型加载器"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化模型加载器
        
        Args:
            cache_dir: 模型缓存目录
        """
        self.project_root = Path(__file__).parent.parent.parent.parent
        
        if cache_dir is None:
            self.cache_dir = self.project_root / ".cache" / "sentence_transformers"
        else:
            self.cache_dir = Path(cache_dir)
        
        self.manager = None
        if SentenceTransformerModelManager:
            self.manager = SentenceTransformerModelManager(self.cache_dir)
    
    def load_model(self, model_name: str, force_online: bool = False) -> Optional[Any]:
        """
        加载 SentenceTransformer 模型
        
        Args:
            model_name: 模型名称
            force_online: 是否强制从网络加载
            
        Returns:
            SentenceTransformer 模型实例
        """
        try:
            from sentence_transformers import SentenceTransformer
            
            if not force_online and self.manager:
                # 尝试使用模型管理器加载（优先本地缓存）
                model = self.manager.load_model(model_name, use_cache=True)
                if model is not None:
                    return model
            
            # 直接从 Hugging Face 加载
            logger.info(f"从网络加载模型: {model_name}")
            return SentenceTransformer(model_name)
            
        except Exception as e:
            logger.error(f"加载模型失败 {model_name}: {e}")
            return None
    
    def is_model_cached(self, model_name: str) -> bool:
        """检查模型是否已缓存"""
        if not self.manager:
            return False
        
        model_cache_path = self.cache_dir / model_name
        return model_cache_path.exists()
    
    def get_model_cache_path(self, model_name: str) -> Optional[Path]:
        """获取模型缓存路径"""
        model_cache_path = self.cache_dir / model_name
        return model_cache_path if model_cache_path.exists() else None


# 全局模型加载器实例
_model_loader = None


def get_model_loader() -> ModelLoader:
    """获取全局模型加载器实例"""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader


def load_sentence_transformer(
    model_name: str, 
    force_online: bool = False,
    cache_dir: Optional[Union[str, Path]] = None
) -> Optional[Any]:
    """
    便捷函数：加载 SentenceTransformer 模型
    
    Args:
        model_name: 模型名称
        force_online: 是否强制从网络加载
        cache_dir: 自定义缓存目录
        
    Returns:
        SentenceTransformer 模型实例
        
    Examples:
        >>> # 加载多语言模型（优先使用本地缓存）
        >>> model = load_sentence_transformer("paraphrase-multilingual-MiniLM-L12-v2")
        
        >>> # 强制从网络加载
        >>> model = load_sentence_transformer("all-MiniLM-L6-v2", force_online=True)
    """
    if cache_dir:
        loader = ModelLoader(Path(cache_dir))
    else:
        loader = get_model_loader()
    
    return loader.load_model(model_name, force_online)


def is_model_cached(model_name: str, cache_dir: Optional[Union[str, Path]] = None) -> bool:
    """
    检查模型是否已缓存
    
    Args:
        model_name: 模型名称
        cache_dir: 自定义缓存目录
        
    Returns:
        是否已缓存
    """
    if cache_dir:
        loader = ModelLoader(Path(cache_dir))
    else:
        loader = get_model_loader()
    
    return loader.is_model_cached(model_name)


# 项目常用模型的便捷加载函数
def load_basic_model(force_online: bool = False) -> Optional[Any]:
    """加载基础英文模型 (all-MiniLM-L6-v2)"""
    return load_sentence_transformer("all-MiniLM-L6-v2", force_online)


def load_multilingual_model(force_online: bool = False) -> Optional[Any]:
    """加载多语言模型 (paraphrase-multilingual-MiniLM-L12-v2)"""
    return load_sentence_transformer("paraphrase-multilingual-MiniLM-L12-v2", force_online)


if __name__ == "__main__":
    # 测试模块功能
    print("🧪 测试模型加载工具...")
    
    loader = get_model_loader()
    
    print(f"缓存目录: {loader.cache_dir}")
    
    # 检查模型缓存状态
    models_to_check = [
        "all-MiniLM-L6-v2",
        "paraphrase-multilingual-MiniLM-L12-v2"
    ]
    
    for model_name in models_to_check:
        cached = is_model_cached(model_name)
        status = "✅ 已缓存" if cached else "❌ 未缓存"
        print(f"{model_name}: {status}")
    
    print("\n💡 使用 scripts/download_sentence_transformers_models.py 来下载模型")
