"""DeckGenerationSystem 单元测试。"""

import json
from typing import Any, Dict, List
from unittest.mock import MagicMock
import pytest
from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import DeckComponent, DrawPileComponent, GenerateDeckAction
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.models.target_type import TargetType
from src.ai_rpg.systems.deck_generation_system import (
    DeckGenerationSystem,
    _sample_keywords,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _card_json(
    name: str = "攻击", target_type: str = TargetType.ENEMY_SINGLE
) -> Dict[str, Any]:
    return {
        "name": name,
        "description": "描述",
        "affixes": [],
        "modifiers": [],
        "playable": True,
        "exhaust": False,
        "damage_dealt": 3,
        "energy_delta": 0,
        "hit_count": 1,
        "target_type": target_type,
    }


def _response_json(cards: List[Dict[str, Any]]) -> str:
    return json.dumps({"cards": cards}, ensure_ascii=False)


def _make_entity(ctx: Context, name: str = "英雄", num_cards: int = 2) -> Entity:
    entity = ctx.create_entity()
    entity._name = name
    entity.add(DeckComponent, name, [], [])
    entity.add(DrawPileComponent, name, [])
    entity.add(GenerateDeckAction, name, num_cards)
    return entity


def _make_chat_client(entity_name: str, response_content: str) -> MagicMock:
    client = MagicMock()
    client.name = entity_name
    client.response_content = response_content
    client.prompt = "prompt"
    client.compressed_prompt = "compressed_prompt"
    client.response_ai_message = AIMessage(content=response_content)
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    return MagicMock(spec=DBGGame)


@pytest.fixture()
def system(mock_game: MagicMock) -> DeckGenerationSystem:
    return DeckGenerationSystem(mock_game)


# ---------------------------------------------------------------------------
# _sample_keywords
# ---------------------------------------------------------------------------


def test_sample_empty_pool_returns_empty() -> None:
    assert _sample_keywords([], k=3) == []


def test_sample_within_pool_no_duplicates() -> None:
    result = _sample_keywords([f"kw{i}" for i in range(10)], k=3)
    assert len(result) == 3 and len(set(result)) == 3


def test_sample_exceeds_pool_allows_replacement() -> None:
    result = _sample_keywords(["a", "b"], k=5)
    assert len(result) == 5 and all(kw in ("a", "b") for kw in result)


# ---------------------------------------------------------------------------
# _process_generation_response
# ---------------------------------------------------------------------------


def test_valid_cards_fill_deck_and_draw_pile(
    ctx: Context, mock_game: MagicMock, system: DeckGenerationSystem
) -> None:
    """合法响应：牌追加到 DeckComponent 和 DrawPileComponent。"""
    entity = _make_entity(ctx, num_cards=2)
    mock_game.get_entity_by_name.return_value = entity

    system._process_generation_response(
        _make_chat_client(
            "英雄", _response_json([_card_json("攻击"), _card_json("防御")])
        )
    )

    assert len(entity.get(DeckComponent).cards) == 2
    assert len(entity.get(DrawPileComponent).cards) == 2


def test_invalid_json_no_raise_draw_pile_empty(
    ctx: Context, mock_game: MagicMock, system: DeckGenerationSystem
) -> None:
    """JSON 解析失败时不抛出，DrawPile 保持空。"""
    entity = _make_entity(ctx, num_cards=2)
    mock_game.get_entity_by_name.return_value = entity

    system._process_generation_response(_make_chat_client("英雄", "not json"))

    assert len(entity.get(DrawPileComponent).cards) == 0
