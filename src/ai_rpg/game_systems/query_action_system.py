from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    QueryAction,
)
from loguru import logger
from ..chroma import get_chroma_db
from ..rag import rag_semantic_search
from loguru import logger


#####################################################################################################################################
@final
class QueryActionSystem(BaseActionReactiveSystem):

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

        related_info = self._get_related_info(query_action.question)
        logger.success(f"🔎 角色发起查询行动，问题: {query_action.question}")
        logger.success(f"💭 角色记忆查询结果: {related_info}")

        if related_info:
            self._game.append_human_message(
                entity,
                f"经过回忆，这些是你回忆到的信息：\n{related_info}\n\n选择性地将这些信息作为参考",
            )
        else:
            self._game.append_human_message(
                entity,
                "没有找到相关背景信息。在接下来的对话中，如果涉及没有找到的或者不在你的上下文中的内容，请诚实地表示不知道，不要编造。",
            )

    ####################################################################################################################################
    def _get_related_info(self, original_message: str) -> str:
        """检索相关信息 - 直接进行检索，能找到就返回，找不到就返回空"""
        try:
            logger.success(f"🔍 直接进行RAG检索: {original_message}")

            # 直接执行RAG检索，不需要路由决策
            return self._query_with_rag(original_message)

        except Exception as e:
            logger.error(f"❌ 相关信息检索失败: {e}")
            return ""  # 失败时返回空

    ####################################################################################################################################
    def _query_with_rag(self, message: str) -> str:
        """RAG查询处理 - 仅执行查询并返回结果"""
        try:
            logger.debug(f"🔍 RAG查询: {message}...")

            # 1. 检查ChromaDB状态
            chroma_db = get_chroma_db()
            if not chroma_db.initialized:
                logger.warning("⚠️ ChromaDB未初始化，返回空结果")
                return ""

            # 2. 执行语义搜索查询
            retrieved_docs, similarity_scores = rag_semantic_search(
                query=message, top_k=3
            )

            # 3. 检查查询结果
            if not retrieved_docs:
                logger.warning("⚠️ 未检索到相关文档，返回空结果")
                return ""

            # 4. 简单格式化查询结果并返回
            result_parts = []
            for i, (doc, score) in enumerate(zip(retrieved_docs, similarity_scores), 1):
                result_parts.append(f"{i}. [相似度: {score:.3f}] {doc}")

            query_result = "\n".join(result_parts)
            logger.success(f"🔍 RAG查询完成，找到 {len(retrieved_docs)} 个相关文档")

            return query_result

        except Exception as e:
            logger.error(f"❌ RAG查询失败: {e}")
            return ""


#####################################################################################################################################
