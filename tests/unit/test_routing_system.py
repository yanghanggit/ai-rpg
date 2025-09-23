"""
路由系统测试

测试重构后的路由决策系统的各个组件。
"""

import pytest

# import sys
# from pathlib import Path
from typing import Dict, Any

# # 添加项目根目录到路径
# project_root = Path(__file__).parent.parent.parent
# sys.path.insert(0, str(project_root))

from src.ai_rpg.rag.routing import (
    RouteStrategy,
    RouteDecision,
    KeywordRouteStrategy,
    SemanticRouteStrategy,
    RouteDecisionManager,
    StrategyWeight,
    create_route_manager_with_strategies,
)

# 导入测试配置数据
from src.ai_rpg.demo.campaign_setting import (
    FANTASY_WORLD_RPG_TEST_ROUTE_KEYWORDS,
    FANTASY_WORLD_RPG_TEST_RAG_TOPICS,
)


# =============================================================================
# 测试专用策略创建函数（与主代码数据隔离）
# =============================================================================


def create_test_alphania_keyword_strategy() -> KeywordRouteStrategy:
    """创建测试专用的艾尔法尼亚关键词策略（数据与主代码隔离）"""

    config = {
        "keywords": FANTASY_WORLD_RPG_TEST_ROUTE_KEYWORDS,
        "threshold": 0.1,  # 与主配置保持一致的阈值
        "case_sensitive": False,
    }

    return KeywordRouteStrategy(config)


def create_test_game_semantic_strategy() -> SemanticRouteStrategy:
    """创建测试专用的游戏语义策略（数据与主代码隔离）"""

    config = {
        "similarity_threshold": 0.5,  # 与主配置保持一致的阈值
        "use_multilingual": True,
        "rag_topics": FANTASY_WORLD_RPG_TEST_RAG_TOPICS,
    }

    return SemanticRouteStrategy(config)


def create_test_route_manager() -> RouteDecisionManager:
    return create_route_manager_with_strategies(
        strategy_configs=[
            (create_test_alphania_keyword_strategy, 0.4),
            (create_test_game_semantic_strategy, 0.6),
        ],
        fallback_to_rag=False,
    )


class TestRouteDecision:
    """测试路由决策结果类"""

    def test_valid_decision(self) -> None:
        """测试有效的路由决策"""
        decision = RouteDecision(
            should_use_rag=True,
            confidence=0.8,
            strategy_name="test",
            metadata={"test": "data"},
        )

        assert decision.should_use_rag is True
        assert decision.confidence == 0.8
        assert decision.strategy_name == "test"
        if decision.metadata:
            assert decision.metadata["test"] == "data"

    def test_invalid_confidence(self) -> None:
        """测试无效的置信度值"""
        with pytest.raises(ValueError):
            RouteDecision(
                should_use_rag=True, confidence=1.5, strategy_name="test"  # 超出范围
            )


class TestKeywordRouteStrategy:
    """测试关键词路由策略"""

    def test_keyword_matching(self) -> None:
        """测试关键词匹配功能"""
        config = {"keywords": ["艾尔法尼亚", "圣剑", "魔法"], "threshold": 0.1}
        strategy = KeywordRouteStrategy(config)

        # 测试匹配的查询
        decision = strategy.should_route_to_rag("艾尔法尼亚的圣剑在哪里？")
        assert decision.should_use_rag is True
        assert decision.confidence > 0.3
        if decision.metadata:
            assert len(decision.metadata["matched_keywords"]) >= 2

    def test_no_keyword_matching(self) -> None:
        """测试无关键词匹配的查询"""
        config = {"keywords": ["艾尔法尼亚", "圣剑", "魔法"], "threshold": 0.1}
        strategy = KeywordRouteStrategy(config)

        # 测试无匹配的查询
        decision = strategy.should_route_to_rag("今天天气怎么样？")
        assert decision.should_use_rag is False
        if decision.metadata:
            assert len(decision.metadata["matched_keywords"]) == 0

    def test_alphania_strategy(self) -> None:
        """测试艾尔法尼亚专用策略"""
        strategy = create_test_alphania_keyword_strategy()  # 使用测试版本

        # 测试游戏相关查询 - 使用实际存在的关键词
        decision = strategy.should_route_to_rag("新奥拉西斯的圣剑和魔法怎么样？")
        # 检查匹配的关键词数量是否合理
        matched_keywords = (
            decision.metadata.get("matched_keywords", []) if decision.metadata else []
        )
        assert (
            len(matched_keywords) > 0
        ), f"应该匹配到关键词，但只匹配到: {matched_keywords}"

        # 检查决策逻辑是否符合配置
        match_ratio = (
            decision.metadata.get("match_ratio", 0) if decision.metadata else 0
        )
        threshold = decision.metadata.get("threshold", 0) if decision.metadata else 0
        expected_rag = match_ratio >= threshold
        assert decision.should_use_rag == expected_rag, (
            f"路由决策不符合阈值逻辑: 匹配率={match_ratio:.3f}, "
            f"阈值={threshold}, 期望={expected_rag}, 实际={decision.should_use_rag}"
        )

        # 测试非游戏查询
        decision = strategy.should_route_to_rag("python编程怎么学？")
        assert decision.should_use_rag is False
        matched_keywords_none = (
            decision.metadata.get("matched_keywords", []) if decision.metadata else []
        )
        assert len(matched_keywords_none) == 0


class TestSemanticRouteStrategy:
    """测试语义路由策略"""

    @pytest.mark.skipif(
        not hasattr(pytest, "semantic_model_available"), reason="需要semantic model可用"
    )
    def test_semantic_matching(self) -> None:
        """测试语义匹配功能"""
        strategy = create_test_game_semantic_strategy()  # 使用测试版本

        # 测试游戏相关查询（语义相关但无关键词）
        decision = strategy.should_route_to_rag("这个虚拟世界的政治结构是什么？")
        # 注意：这个测试结果依赖于模型的实际表现

        assert decision.strategy_name == "semantic_matcher"
        assert 0.0 <= decision.confidence <= 1.0


class TestRouteDecisionManager:
    """测试路由决策管理器"""

    def test_combined_decision(self) -> None:
        """测试组合决策"""
        # 创建测试策略
        keyword_strategy = create_test_alphania_keyword_strategy()  # 使用测试版本

        # 创建管理器
        manager = RouteDecisionManager([StrategyWeight(keyword_strategy, 1.0)])

        # 测试决策 - 使用存在的关键词
        decision = manager.make_decision("新奥拉西斯的魔法系统如何？")
        assert decision.strategy_name == "combined"
        if decision.metadata:
            assert "strategies_used" in decision.metadata

    def test_fallback_strategy(self) -> None:
        """测试回退策略"""

        # 创建会失败的策略
        class FailingStrategy(RouteStrategy):
            def should_route_to_rag(
                self, query: str, context: Dict[str, Any] | None = None
            ) -> RouteDecision:
                raise Exception("策略失败")

        failing_strategy = FailingStrategy("failing")

        manager = RouteDecisionManager([StrategyWeight(failing_strategy, 1.0)])

        # 应该回退到默认策略
        decision = manager.make_decision("任何查询")
        assert decision.strategy_name == "fallback"

    def test_default_manager(self) -> None:
        """测试默认管理器"""
        # 使用核心函数直接创建具体策略配置的管理器（使用测试版本）
        manager = create_route_manager_with_strategies(
            strategy_configs=[
                (create_test_alphania_keyword_strategy, 0.4),  # 使用测试版本
                (create_test_game_semantic_strategy, 0.6),  # 使用测试版本
            ],
            fallback_to_rag=False,
        )

        # 测试游戏相关查询 - 使用存在的关键词
        decision = manager.make_decision("新奥拉西斯的历史和封印之塔")
        assert decision.should_use_rag is True

        # 测试一般查询
        decision = manager.make_decision("你好")
        # 结果取决于策略配置


class TestIntegration:
    """集成测试"""

    def test_router_node_replacement(self) -> None:
        """测试路由节点的替换"""
        # 这个测试验证新的路由系统能否替代原有的router_node
        from src.ai_rpg.deepseek.unified_chat_graph import (
            UnifiedState,
        )

        from src.ai_rpg.deepseek import create_deepseek_llm

        # 创建路由管理器实例
        manager = create_test_route_manager()
        assert manager is not None

        llm = create_deepseek_llm()

        # 创建测试状态
        test_state: UnifiedState = {
            "messages": [],
            "user_query": "",
            "route_decision": "",
            "retrieved_docs": None,
            "enhanced_context": None,
            "similarity_scores": None,
            "confidence_score": 0.0,
            "processing_mode": "",
            "route_manager": manager,  # 直接设置路由管理器
            "llm": llm,  # 添加LLM实例到状态中
        }

        # 测试一些典型查询 - 使用存在的关键词
        test_queries = [
            "新奥拉西斯的圣剑有哪些？",
            "晨曦之刃的属性是什么？",
            "今天天气怎么样？",
            "你好，我是新手玩家",
        ]

        for query in test_queries:
            decision = manager.make_decision(query)
            assert isinstance(decision, RouteDecision)
            assert 0.0 <= decision.confidence <= 1.0
            assert decision.strategy_name == "combined"


if __name__ == "__main__":
    # 手动测试模式
    print("🧪 路由系统手动测试")

    # 测试关键词策略
    print("\n=== 关键词策略测试 ===")
    keyword_strategy = create_test_alphania_keyword_strategy()  # 使用测试版本

    test_queries = [
        "新奥拉西斯的魔法系统有哪些？",
        "晨曦之刃是什么武器？",
        "今天天气很好",
        "Python编程难吗？",
    ]

    for query in test_queries:
        decision = keyword_strategy.should_route_to_rag(query)
        print(f"查询: {query}")
        print(f"结果: RAG={decision.should_use_rag}, 置信度={decision.confidence:.3f}")
        if decision.metadata and decision.metadata.get("matched_keywords"):
            print(f"匹配关键词: {decision.metadata['matched_keywords']}")
        print()

    # 测试完整路由管理器
    print("\n=== 完整路由管理器测试 ===")
    # 使用核心函数创建具体策略配置的管理器（使用测试版本）
    manager = create_route_manager_with_strategies(
        strategy_configs=[
            (create_test_alphania_keyword_strategy, 0.4),  # 使用测试版本
            (create_test_game_semantic_strategy, 0.6),  # 使用测试版本
        ],
        fallback_to_rag=False,
    )

    for query in test_queries:
        decision = manager.make_decision(query)
        print(f"查询: {query}")
        print(
            f"最终决策: RAG={decision.should_use_rag}, 置信度={decision.confidence:.3f}"
        )
        strategies = (
            decision.metadata.get("strategies_used", []) if decision.metadata else []
        )
        print(f"使用策略: {strategies}")
        print()

    print("✅ 手动测试完成")
