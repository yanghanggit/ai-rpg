"""
数据库模型注册模块

这个模块负责导入所有数据库模型，确保它们被注册到SQLAlchemy的Base.metadata中。
通过集中管理所有模型导入，避免在业务代码中出现未使用的导入警告。
"""

from loguru import logger

# 导入所有数据库模型以确保它们被注册到Base.metadata中
from .vector_document import VectorDocumentDB

# 可以在这里添加其他模型的导入
# from .other_model import OtherModel

__all__ = [
    "VectorDocumentDB",
    "register_all_models",
]


def register_all_models() -> None:
    """
    注册所有数据库模型

    这个函数确保所有模型都被正确导入和注册。
    虽然模型在导入时就会自动注册，但这个函数提供了一个明确的入口点。
    """
    logger.debug("数据库模型注册完成")
    logger.debug(f"已注册模型: VectorDocumentDB")
    # 可以在这里添加其他模型的日志
