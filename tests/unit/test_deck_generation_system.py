"""DeckGenerationSystem 单元测试。

覆盖范围：
  - _sample_keywords        （纯函数，采样逻辑）
  - _build_design_principle_prompt  （纯函数，关键词约束段落）
  - _generate_deck_prompt   （纯函数，含 f-string 花括号回归测试）
  - DeckGenerationSystem._process_generation_response（LLM 响应解析 + 组件写入）

不覆盖：
  - react()：依赖 DeepSeekClient.batch_chat LLM 网络调用，属集成层
  - Pydantic 模型字段（框架本身已验证）
"""

import json
from typing import List, Dict, Any
from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    DeckComponent,
    DrawPileComponent,
)
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.models.target_type import TargetType
from src.ai_rpg.systems.deck_generation_system import (
    DeckGenerationSystem,
    _sample_keywords,
)
from src.ai_rpg.systems.card_prompt_builders import (
    build_design_principle_prompt,
    generate_deck_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_keywords(n: int) -> List[str]:
    """生成 n 个描述各不相同的关键词列表。"""
    return [f"关键词{i}" for i in range(n)]


def _make_stats(hp: int = 10, attack: int = 5, defense: int = 3) -> CharacterStats:
    return CharacterStats(hp=hp, max_hp=hp, attack=attack, defense=defense)


def _make_actor_entity(context: Context, name: str = "test_actor") -> Entity:
    """创建挂载 DeckComponent + DrawPileComponent 的实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(DeckComponent, name, [], [])
    entity.add(DrawPileComponent, name, [])
    return entity


def _make_mock_game() -> MagicMock:
    game = MagicMock(spec=TCGGame)
    return game


def _build_valid_card_json(
    name: str = "测试攻击",
    target_type: str = TargetType.ENEMY_SINGLE,
    damage_dealt: int = 5,
) -> Dict[str, Any]:
    return {
        "name": name,
        "description": "对单一敌人造成伤害",
        "affixes": [],
        "modifiers": [],
        "playable": True,
        "exhaust": False,
        "damage_dealt": damage_dealt,
        "energy_delta": 0,
        "hit_count": 1,
        "target_type": target_type,
    }


def _wrap_cards_response(cards: List[Dict[str, Any]]) -> str:
    """将卡牌列表包装为 LLM 响应格式（纯 JSON，无 code block）。"""
    return json.dumps({"cards": cards}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Group 1 — _sample_keywords
# ---------------------------------------------------------------------------


class TestSampleKeywords:

    def test_empty_keywords_returns_empty(self) -> None:
        result = _sample_keywords([], k=3)
        assert result == []

    def test_k_within_pool_returns_exact_k(self) -> None:
        keywords = _make_keywords(5)
        result = _sample_keywords(keywords, k=3)
        assert len(result) == 3
        # 所有返回项均来自原池
        assert all(kw in keywords for kw in result)

    def test_k_exceeds_pool_returns_k_with_replacement(self) -> None:
        keywords = _make_keywords(2)
        result = _sample_keywords(keywords, k=5)
        assert len(result) == 5
        assert all(kw in keywords for kw in result)

    def test_k_equals_pool_returns_all(self) -> None:
        keywords = _make_keywords(3)
        result = _sample_keywords(keywords, k=3)
        assert len(result) == 3
        assert sorted(result) == sorted(keywords)


# ---------------------------------------------------------------------------
# Group 2 — _build_design_principle_prompt
# ---------------------------------------------------------------------------


class TestBuildDesignPrinciplePrompt:

    def test_no_keywords_references_num_cards(self) -> None:
        result = build_design_principle_prompt(num_cards=4, keywords=[])
        assert "4" in result

    def test_keywords_without_dice_descriptions_appear(self) -> None:
        keywords = _make_keywords(2)
        result = build_design_principle_prompt(num_cards=2, keywords=keywords)
        for kw in keywords:
            assert kw in result

    def test_keywords_without_dice_no_dice_label(self) -> None:
        """dice_rolls 为空时，输出中不含"骰值"字样。"""
        keywords = _make_keywords(2)
        result = build_design_principle_prompt(
            num_cards=2, keywords=keywords, dice_rolls=[]
        )
        assert "骰值" not in result

    def test_keywords_with_matching_dice_appear_in_output(self) -> None:
        keywords = _make_keywords(2)
        dice_rolls = [42, 77]
        result = build_design_principle_prompt(
            num_cards=2, keywords=keywords, dice_rolls=dice_rolls
        )
        assert "42" in result
        assert "77" in result

    def test_keywords_with_mismatched_dice_ignored(self) -> None:
        """len(dice_rolls) != len(keywords) 时骰值不应出现。"""
        keywords = _make_keywords(3)
        dice_rolls = [10]  # 长度不匹配
        result = build_design_principle_prompt(
            num_cards=3, keywords=keywords, dice_rolls=dice_rolls
        )
        assert "骰值" not in result


# ---------------------------------------------------------------------------
# Group 3 — _generate_deck_prompt
# ---------------------------------------------------------------------------


class TestGenerateDeckPrompt:

    def test_no_fstring_format_error_regression(self) -> None:
        """回归测试：f-string 中的 JSON 示例花括号转义正确，调用不应抛出 ValueError。"""
        stats = _make_stats()
        try:
            result = generate_deck_prompt(actor_stats=stats, num_cards=3)
        except ValueError as e:
            pytest.fail(f"_generate_deck_prompt raised ValueError: {e}")
        assert isinstance(result, str)

    def test_prompt_contains_literal_json_braces(self) -> None:
        """输出字符串中必须有字面量花括号（JSON 示例）。"""
        stats = _make_stats()
        result = generate_deck_prompt(actor_stats=stats, num_cards=2)
        assert "{" in result
        assert "}" in result

    def test_prompt_contains_actor_stats(self) -> None:
        stats = _make_stats(hp=20, attack=8, defense=4)
        result = generate_deck_prompt(actor_stats=stats, num_cards=1)
        assert "20" in result
        assert "8" in result
        assert "4" in result

    def test_prompt_num_cards_reflected(self) -> None:
        stats = _make_stats()
        result = generate_deck_prompt(actor_stats=stats, num_cards=5)
        assert "5" in result


# ---------------------------------------------------------------------------
# Group 4 — DeckGenerationSystem._process_generation_response
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    return _make_mock_game()


@pytest.fixture()
def system(mock_game: MagicMock) -> DeckGenerationSystem:
    return DeckGenerationSystem(mock_game)


def _make_chat_client_mock(response_content: str) -> MagicMock:
    client = MagicMock()
    client.response_content = response_content
    return client


class TestProcessGenerationResponse:

    def test_valid_response_fills_draw_pile(
        self, context: Context, mock_game: MagicMock, system: DeckGenerationSystem
    ) -> None:
        entity = _make_actor_entity(context)
        cards = [_build_valid_card_json(f"卡牌{i}") for i in range(3)]
        client = _make_chat_client_mock(_wrap_cards_response(cards))

        system._process_generation_response(entity, client, num_cards=3)

        draw_pile = entity.get(DrawPileComponent)
        assert draw_pile is not None
        assert len(draw_pile.cards) == 3

    def test_valid_response_appends_to_deck_component(
        self, context: Context, mock_game: MagicMock, system: DeckGenerationSystem
    ) -> None:
        entity = _make_actor_entity(context)
        cards = [_build_valid_card_json(f"卡牌{i}") for i in range(2)]
        client = _make_chat_client_mock(_wrap_cards_response(cards))

        system._process_generation_response(entity, client, num_cards=2)

        deck_comp = entity.get(DeckComponent)
        assert deck_comp is not None
        assert len(deck_comp.cards) == 2

    def test_invalid_target_type_skips_card_and_warns(
        self, context: Context, mock_game: MagicMock, system: DeckGenerationSystem
    ) -> None:
        """target_type 非法的卡应被丢弃，并触发 add_human_message 警告。"""
        cards = [
            _build_valid_card_json("合法卡", target_type=TargetType.ENEMY_SINGLE),
            _build_valid_card_json("非法卡", target_type="invalid_type"),
        ]
        client = _make_chat_client_mock(_wrap_cards_response(cards))
        entity = _make_actor_entity(context)

        system._process_generation_response(entity, client, num_cards=2)

        # 只有 1 张合法卡进入堆
        draw_pile = entity.get(DrawPileComponent)
        assert draw_pile is not None
        assert len(draw_pile.cards) == 1

        # add_human_message 被调用 2 次：1次 target_type 非法警告 + 1次 context 写回
        assert mock_game.add_human_message.call_count == 2
        # 第一次调用是警告消息（不含 deck_generation_full_prompt kwarg）
        first_call_kwargs = mock_game.add_human_message.call_args_list[0].kwargs
        assert "deck_generation_full_prompt" not in first_call_kwargs
        # 第二次调用是 context 写回（含 deck_generation_full_prompt kwarg）
        second_call_kwargs = mock_game.add_human_message.call_args_list[1].kwargs
        assert "deck_generation_full_prompt" in second_call_kwargs

    def test_malformed_json_no_crash_draw_pile_empty(
        self, context: Context, mock_game: MagicMock, system: DeckGenerationSystem
    ) -> None:
        """非法 JSON 不应抛出异常，DrawPile 保持空。"""
        client = _make_chat_client_mock("这不是合法的 JSON {{{")
        entity = _make_actor_entity(context)

        try:
            system._process_generation_response(entity, client, num_cards=2)
        except Exception as e:
            pytest.fail(f"应吞噬异常，但抛出了: {e}")

        draw_pile = entity.get(DrawPileComponent)
        assert draw_pile is not None
        assert len(draw_pile.cards) == 0

    def test_draw_pile_cards_are_copies_not_same_object(
        self, context: Context, mock_game: MagicMock, system: DeckGenerationSystem
    ) -> None:
        """DrawPile 中的卡应为 model_copy() 副本，与 DeckComponent 中的对象不同。"""
        cards = [_build_valid_card_json("卡牌A")]
        client = _make_chat_client_mock(_wrap_cards_response(cards))
        entity = _make_actor_entity(context)

        system._process_generation_response(entity, client, num_cards=1)

        deck_comp = entity.get(DeckComponent)
        draw_pile = entity.get(DrawPileComponent)
        assert deck_comp is not None
        assert draw_pile is not None
        assert deck_comp.cards[0] is not draw_pile.cards[0]
