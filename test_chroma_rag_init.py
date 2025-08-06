#!/usr/bin/env python3
"""
ChromaDB RAG系统初始化测试脚本

用于验证改造后的RAG系统是否能正常初始化和运行
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from loguru import logger
from src.multi_agents_game.chat_services.chat_deepseek_rag_graph import (
    ChromaRAGDatabase,
    get_chroma_db,
    initialize_rag_system,
)


def test_chromadb_initialization():
    """测试ChromaDB初始化"""
    logger.info("🧪 开始测试ChromaDB RAG系统初始化...")

    try:
        # 测试ChromaDB实例创建
        chroma_db = get_chroma_db()
        logger.info(f"✅ ChromaDB实例创建成功: {type(chroma_db)}")

        # 测试完整初始化
        success = initialize_rag_system()

        if success:
            logger.success("🎉 ChromaDB RAG系统初始化测试通过！")

            # 测试语义搜索
            test_query = "圣剑的能力"
            docs, scores = chroma_db.semantic_search(test_query, top_k=3)

            logger.info(f"🔍 测试语义搜索: '{test_query}'")
            for i, (doc, score) in enumerate(zip(docs, scores)):
                logger.info(f"  [{i+1}] 相似度: {score:.3f}, 内容: {doc[:50]}...")

            return True
        else:
            logger.error("❌ ChromaDB RAG系统初始化失败")
            return False

    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = test_chromadb_initialization()
    sys.exit(0 if success else 1)
