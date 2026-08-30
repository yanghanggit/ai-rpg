"""knowledge_query.search_knowledge_base 单元测试。"""

from unittest.mock import MagicMock, patch

from src.ai_rpg.systems.knowledge_query import search_knowledge_base


#######################################################################################################################################
def test_formats_search_results() -> None:
    game = MagicMock()
    game.name = "测试游戏"

    with (
        patch(
            "src.ai_rpg.systems.knowledge_query.search_documents",
            return_value=(["文档A", "文档B"], [0.9, 0.5]),
        ) as mock_search,
        patch("src.ai_rpg.systems.knowledge_query.embedding_model", "fake_model"),
    ):
        result = search_knowledge_base(game, "问题", top_k=3)

    assert "1. [相似度: 0.900] 文档A" in result
    assert "2. [相似度: 0.500] 文档B" in result
    assert "相似度参考" in result
    mock_search.assert_called_once_with(
        query="问题",
        collection="测试游戏",
        embedding_model="fake_model",
        top_k=3,
    )


#######################################################################################################################################
def test_no_results_returns_hint() -> None:
    game = MagicMock()
    game.name = "测试游戏"

    with patch(
        "src.ai_rpg.systems.knowledge_query.search_documents",
        return_value=([], []),
    ):
        result = search_knowledge_base(game, "问题")

    assert "未检索到相关信息" in result


#######################################################################################################################################
def test_exception_returns_failure_message() -> None:
    game = MagicMock()
    game.name = "测试游戏"

    with patch(
        "src.ai_rpg.systems.knowledge_query.search_documents",
        side_effect=RuntimeError("boom"),
    ):
        result = search_knowledge_base(game, "问题")

    assert "检索失败" in result
