"""
关键词路由策略

基于关键词匹配的路由决策策略，支持配置化关键词管理。
"""

from typing import Any, Dict, Optional, Set

from loguru import logger

from .route_strategy import RouteDecision, RouteStrategy


class KeywordRouteStrategy(RouteStrategy):
    """基于关键词匹配的路由策略"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("keyword_matcher", config)
        self.keywords: Set[str] = set()
        self.threshold = self.get_config_value("threshold", 0.5)
        self.case_sensitive = self.get_config_value("case_sensitive", False)

    def _do_initialize(self) -> None:
        """初始化关键词集合"""
        keywords_list = self.get_config_value("keywords", [])

        if isinstance(keywords_list, list):
            # 处理大小写敏感性
            if self.case_sensitive:
                self.keywords = set(keywords_list)
            else:
                self.keywords = set(keyword.lower() for keyword in keywords_list)

        logger.info(f"🔑 关键词路由策略加载了 {len(self.keywords)} 个关键词")
        logger.debug(f"🔑 关键词列表样例: {list(self.keywords)[:5]}...")

    def should_route_to_rag(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> RouteDecision:
        """基于关键词匹配进行路由决策"""
        if not self.is_initialized:
            self.initialize()

        # 预处理查询文本
        processed_query = query if self.case_sensitive else query.lower()

        # 计算匹配的关键词
        matched_keywords = []
        for keyword in self.keywords:
            if keyword in processed_query:
                matched_keywords.append(keyword)

        # 计算匹配度
        match_ratio = (
            len(matched_keywords) / len(self.keywords) if self.keywords else 0.0
        )

        # 基于阈值做决策
        should_use_rag = match_ratio >= self.threshold

        # 置信度计算：基于匹配数量和比例
        confidence = min(0.9, 0.3 + match_ratio * 0.6)

        logger.debug(
            f"🔑 关键词匹配: 找到 {len(matched_keywords)} 个匹配，"
            f"匹配率 {match_ratio:.3f}，阈值 {self.threshold}"
        )

        return RouteDecision(
            should_use_rag=should_use_rag,
            confidence=confidence,
            strategy_name=self.name,
            metadata={
                "matched_keywords": matched_keywords,
                "match_ratio": match_ratio,
                "threshold": self.threshold,
                "total_keywords": len(self.keywords),
            },
        )


def create_alphania_keyword_strategy() -> KeywordRouteStrategy:
    """创建艾尔法尼亚世界专用的关键词策略"""

    # 艾尔法尼亚世界关键词配置
    alphania_keywords = [
        # 地名和世界设定
        "艾尔法尼亚",
        "阿斯特拉王国",
        "月桂森林联邦",
        "铁爪部族联盟",
        "封印之塔",
        "贤者之塔",
        "水晶城",
        "暗影墓地",
        "星辰神殿",
        # 重要物品和角色
        "圣剑",
        "晨曦之刃",
        "魔王",
        "玛拉凯斯",
        "黯蚀之主",
        "勇者",
        "莉莉丝",
        # 种族和职业
        "精灵",
        "兽人",
        "龙族",
        "矮人",
        "冒险者",
        "骑士",
        "法师",
        "战士",
        # 魔法和技能
        "火焰",
        "冰霜",
        "雷电",
        "治愈",
        "暗影",
        "净化之光",
        "审判之炎",
        "希望守护",
        # 组织和物品
        "冒险者公会",
        "暴风雪团",
        "时之沙漏",
        "生命之泉",
        "星辰钢",
        "魔法药水",
        # 通用游戏术语
        "王国",
        "联邦",
        "部族",
        "遗迹",
        "地下城",
        "魔法",
        "技能",
        "装备",
        "等级",
    ]

    config = {
        "keywords": alphania_keywords,
        "threshold": 0.1,  # 较低阈值，只要匹配到关键词就启用RAG
        "case_sensitive": False,
    }

    return KeywordRouteStrategy(config)
