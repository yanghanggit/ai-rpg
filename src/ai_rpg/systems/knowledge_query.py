"""共享知识库检索工具函数。"""

from typing import Final

from loguru import logger

from ..embedding_model import embedding_model
from ..game.dbg_game import DBGGame
from ..rag import search_documents


DEFAULT_TOP_K: Final[int] = 5


#######################################################################################################################################
def search_knowledge_base(
    game: DBGGame,
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """对公共知识库执行语义检索，返回格式化的相似度结果字符串。"""

    try:
        docs, scores = search_documents(
            query=question,
            collection=game.name,
            embedding_model=embedding_model,
            top_k=top_k,
        )

        if not docs:
            return "（知识库中未检索到相关信息）"

        lines = [
            f"{i}. [相似度: {score:.3f}] {doc}"
            for i, (doc, score) in enumerate(zip(docs, scores), 1)
        ]
        lines.append("\n相似度参考：>0.70 高度相关；0.55~0.70 中等相关；<0.55 低相关。")
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        return "知识库检索失败，请稍后重试。"


#######################################################################################################################################
