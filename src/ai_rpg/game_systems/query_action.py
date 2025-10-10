"""
RAG查询服务 - 提供独立的查询功能，可被其他系统调用
"""

from ..chroma import get_chroma_db
from ..rag import search_similar_documents
from ..embedding_model.sentence_transformer import get_embedding_model
from loguru import logger


###################################################################################################################################
class QueryService:
    """RAG查询服务 - 专门处理知识库查询"""

    def __init__(self) -> None:
        self._initialized = False

    ####################################################################################################################################
    def initialize(self) -> None:
        """初始化查询服务"""
        if self._initialized:
            return

        try:
            # 检查ChromaDB是否可用
            chroma_db = get_chroma_db()
            if chroma_db.initialized:
                self._initialized = True
                logger.debug("🎯 QueryService 初始化完成")
            else:
                logger.warning("⚠️ ChromaDB未初始化，QueryService初始化跳过")

        except Exception as e:
            logger.error(f"❌ QueryService 初始化失败: {e}")

    ####################################################################################################################################
    def query(self, query_text: str) -> str:
        """
        执行查询 - 直接进行RAG检索

        Args:
            query_text: 查询文本

        Returns:
            查询结果字符串
        """
        if not self._initialized:
            self.initialize()

        try:
            # 直接执行RAG查询
            return self._execute_rag_query(query_text)

        except Exception as e:
            logger.error(f"❌ 查询执行失败: {e}")
            return ""

    ####################################################################################################################################
    def _execute_rag_query(self, query_text: str) -> str:
        """执行RAG查询"""
        try:
            logger.debug(f"🔍 RAG查询: {query_text}...")

            # 1. 检查ChromaDB状态
            chroma_db = get_chroma_db()
            if not chroma_db.initialized:
                logger.warning("⚠️ ChromaDB未初始化，返回空结果")
                return ""

            # 1.5. 获取嵌入模型
            embedding_model = get_embedding_model()
            if embedding_model is None:
                logger.warning("⚠️ 嵌入模型未初始化，返回空结果")
                return ""

            # 1.6. 检查collection是否可用
            if chroma_db.collection is None:
                logger.warning("⚠️ ChromaDB collection未初始化，返回空结果")
                return ""

            # 2. 执行语义搜索查询
            retrieved_docs, similarity_scores = search_similar_documents(
                query=query_text,
                collection=chroma_db.collection,
                embedding_model=embedding_model,
                top_k=5,
            )

            # 3. 检查查询结果
            if not retrieved_docs:
                logger.warning("⚠️ 未检索到相关文档，返回空结果")
                return ""

            # 4. 格式化查询结果并返回
            result_parts = []
            for i, (doc, score) in enumerate(zip(retrieved_docs, similarity_scores), 1):
                result_parts.append(f"{i}. [相似度: {score:.3f}] {doc}")

            query_result = "\n".join(result_parts)
            logger.success(f"🔍 RAG查询完成，找到 {len(retrieved_docs)} 个相关文档")

            return query_result

        except Exception as e:
            logger.error(f"❌ RAG查询失败: {e}")
            return ""


###################################################################################################################################
# 全局查询服务实例
_query_service = QueryService()


def get_query_service() -> QueryService:
    """获取查询服务实例"""
    return _query_service


#####################################################################################################################################
def quick_query(query_text: str) -> str:
    """
    便捷查询函数 - 可在任何地方直接调用

    Args:
        query_text: 查询文本

    Returns:
        查询结果字符串
    """
    return _query_service.query(query_text)


#####################################################################################################################################
