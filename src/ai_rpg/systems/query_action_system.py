from typing import Final, final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    QueryAction,
)
from loguru import logger
from loguru import logger
from ..embedding_model import (
    multilingual_model,
)
from ..chroma import get_custom_collection
from ..rag import search_documents
from ..game.tcg_game import TCGGame


#############################################################################################################################
def _build_query_result_message(question: str, related_info: str | None) -> str:
    """构建向量数据库查询结果的提示词消息

    Args:
        question: 查询的问题
        related_info: 检索到的相关信息，None表示未检索到

    Returns:
        格式化的提示词消息
    """
    if related_info:
        return (
            f"关于「{question}」，从向量数据库检索到以下信息：\n{related_info}\n\n"
            f"这些是向量数据库中**目前**存储的相关信息，可根据需要参考。避免对同一问题重复查询。"
        )
    else:
        return f"关于「{question}」：向量数据库中**目前**没有相关信息。"


#####################################################################################################################################
@final
class QueryActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: Final[TCGGame] = game_context

    #############################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(QueryAction): GroupEvent.ADDED}

    #############################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(QueryAction)

    #############################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    #############################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        query_action = entity.get(QueryAction)
        assert query_action is not None

        related_info = self._get_related_info(entity, query_action.question)
        logger.success(f"🔎 角色发起查询行动，问题: {query_action.question}")
        logger.success(f"💭 角色记忆查询结果: {related_info}")

        # 构建并发送查询结果消息
        message = _build_query_result_message(
            query_action.question, related_info if related_info else None
        )
        self._game.add_human_message(entity, message)

    ####################################################################################################################################
    def _get_related_info(self, entity: Entity, original_message: str) -> str:
        """RAG检索相关信息 - 查询公共知识库"""
        try:
            logger.success(f"🔍 RAG检索: {original_message}")

            # 查询公共知识库
            logger.info(f"📚 查询公共知识库（游戏: {self._game.name}）...")
            docs, scores = search_documents(
                query=original_message,
                collection=get_custom_collection(self._game.name),
                embedding_model=multilingual_model,
                top_k=3,
            )

            # 检查查询结果
            if not docs:
                logger.warning("⚠️ 未检索到任何相关文档，返回空结果")
                return ""

            # 格式化结果
            result_parts = []
            for i, (doc, score) in enumerate(zip(docs, scores), 1):
                result_parts.append(f"{i}. [相似度: {score:.3f}] {doc}")

            query_result = "\n".join(result_parts)
            logger.success(f"🔍 RAG查询完成，共找到 {len(docs)} 条相关知识")

            return query_result

        except Exception as e:
            logger.error(f"❌ RAG查询失败: {e}")
            return ""


#####################################################################################################################################
