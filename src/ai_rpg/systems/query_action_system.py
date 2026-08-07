"""QueryActionSystem — 角色检索行动处理系统"""

from typing import Final, Optional, final, override, Dict, List
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..models import (
    HumanMessage,
    QueryAction,
)
from loguru import logger
from ..embedding_model import (
    multilingual_model,
)
from ..chroma import get_custom_collection, search_documents
from ..game.dbg_game import DBGGame


#############################################################################################################################
def _build_query_result_message(
    actor: str, question: str, related_info: Optional[str] = None
) -> str:
    """构建向量数据库查询结果的提示词消息"""
    if related_info:

        return f"""# {actor} 发起检索行动，问题: 「{question}」

## 查询结果

{related_info}

## 相似度参考

- **> 0.70**：高度相关，可直接参考
- **0.55 ~ 0.70**：中等相关，建议结合上下文判断后再使用
- **< 0.55**：低相关，知识库中可能没有直接对应信息，由你自行决定是否参照

## 提示

- 这些是向量数据库中**目前**存储的相关信息。避免对同一问题重复查询。"""

    else:

        return f"""# {actor} 发起检索行动，问题: 「{question}」

## 查询结果

向量数据库中**目前**没有相关信息。"""


#####################################################################################################################################
@final
class QueryActionSystem(ReactiveProcessor):

    def __init__(self, game: DBGGame, top_k: int = 5) -> None:
        super().__init__(game)
        self._game: Final[DBGGame] = game
        self._top_k: Final[int] = top_k  # RAG检索返回的结果数量

    #############################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(QueryAction): GroupEvent.ADDED}

    #############################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(QueryAction)

    #############################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    #############################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        """处理单个实体的查询行动。"""
        query_action = entity.get(QueryAction)
        assert query_action is not None

        related_info = self._get_related_info(entity, query_action.question)
        logger.success(f"🔎 角色发起查询行动，问题: {query_action.question}")
        logger.success(f"💭 角色记忆查询结果: {related_info}")

        # 构建并发送查询结果消息
        message = _build_query_result_message(
            actor=entity.name,
            question=query_action.question,
            related_info=related_info if related_info else None,
        )

        # 将查询结果作为系统消息发送给角色，供后续决策参考
        self._game.add_human_message(entity, HumanMessage(content=message))

    ####################################################################################################################################
    def _get_related_info(self, entity: Entity, original_message: str) -> str:
        """对公共知识库执行语义检索，返回格式化的相似度结果字符串。"""
        try:
            logger.success(f"🔍 RAG检索: {original_message}")

            # 查询公共知识库
            logger.info(f"📚 查询公共知识库（游戏: {self._game.name}）...")
            docs, scores = search_documents(
                query=original_message,
                collection=get_custom_collection(self._game.name),
                embedding_model=multilingual_model,
                top_k=self._top_k,
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
