"""`AssembleDungeonDeckSystem` 单测：显式牌库规格、艺术锚点注入、组件合并不丢。

设计 / 选型 / 物化都在模块边界被替换；只测接线与回退语义。
"""

from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas import dump_components
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    Actor,
    ActorType,
    Card,
    CharacterStats,
    DeckComponent,
    MotifComponent,
    TargetType,
)
from ai_rpg.pgsql import CardPrototypeIndexEntry
from ai_rpg.systems import assemble_dungeon_deck_system as deck_module
from ai_rpg.systems.assemble_dungeon_deck_system import (
    DECK_SIZE,
    AssembleDungeonDeckSystem,
)
from ai_rpg.systems.card_common import (
    Candidate,
    DesignOutcome,
    SelectionOutcome,
    read_motif_from_components,
)

_MOTIF = "**母题**: 独眼的猎手\n**意象**: 泥与血痂、肌腱"


def _actor(motif: str = _MOTIF) -> Actor:
    components = (
        dump_components(MotifComponent(name="怪物.头狼", motif=motif)) if motif else {}
    )
    return Actor(
        name="怪物.头狼",
        type=ActorType.MONSTER,
        profile="独眼的巨狼",
        base_body="灰褐色的皮毛",
        system_message="# 怪物.头狼",
        character_stats=CharacterStats(),
        components=components,
    )


def _entry(prototype_id: str) -> CardPrototypeIndexEntry:
    return {
        "prototype_id": prototype_id,
        "card_type": "手牌",
        "tier": "basic",
        "archetype": "攻击端",
        "archetype_subtype": "前端伤害",
        "name": "原型",
        "summary": "摘要",
        "keywords": [],
    }


def _candidate(prototype_id: str) -> Candidate:
    return Candidate(
        card=Card(
            name=f"设计后的{prototype_id}",
            description="",
            target_type=TargetType.SINGLE,
            source="怪物.头狼",
        ),
        archetype="",
        archetype_subtype="",
        summary="",
        design="",
    )


@pytest.fixture()
def system() -> AssembleDungeonDeckSystem:
    return AssembleDungeonDeckSystem(MagicMock(spec=DBGGame))


#######################################################################################################################################
def test_read_motif_from_components_handles_missing_shapes() -> None:
    assert read_motif_from_components({}) == ""
    assert read_motif_from_components({"MotifComponent": None}) == ""
    assert read_motif_from_components({"MotifComponent": {"motif": 123}}) == ""
    assert read_motif_from_components({"MotifComponent": {"motif": _MOTIF}}) == _MOTIF


#######################################################################################################################################
async def test_explicit_deck_spec_skips_selection(
    system: AssembleDungeonDeckSystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    """显式规格：跳过 LLM 选型，按规格物化；艺术锚点照常注入设计会话。"""
    spec = [f"proto.{i}" for i in range(DECK_SIZE)]
    materialized: List[str] = []
    captured: Dict[str, Any] = {}

    monkeypatch.setattr(
        deck_module,
        "select_prototypes_for_actor",
        lambda *args, **kwargs: pytest.fail("显式规格不应调用 LLM 选型"),
    )

    def _fake_materialize(prototype_id: str, source: str) -> Candidate:
        materialized.append(prototype_id)
        return _candidate(prototype_id)

    monkeypatch.setattr(deck_module, "materialize_candidate", _fake_materialize)

    async def _fake_design(*args: Any, **kwargs: Any) -> DesignOutcome:
        captured.update(kwargs)
        total = len(kwargs["candidates"])
        return DesignOutcome(ok=True, designed=total, total=total, affixes=1)

    monkeypatch.setattr(deck_module, "design_cards_for_actor", _fake_design)

    cards, is_fallback = await system._build_cards(_actor(), [_entry("proto.x")], spec)

    assert is_fallback is False
    assert materialized == spec
    assert len(cards) == DECK_SIZE
    assert captured["actor_motif"] == _MOTIF


async def test_explicit_deck_spec_wrong_count_falls_back(
    system: AssembleDungeonDeckSystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        deck_module,
        "make_default_deck_cards",
        lambda owner: [Card(name="默认牌", description="", source=owner)],
    )

    cards, is_fallback = await system._build_cards(
        _actor(), [_entry("proto.x")], ["proto.only"]
    )

    assert is_fallback is True
    assert [c.name for c in cards] == ["默认牌"]


#######################################################################################################################################
async def test_selection_path_passes_motif_to_design(
    system: AssembleDungeonDeckSystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    """默认口径（无显式规格）仍走 LLM 选型，并把艺术锚点带进设计。"""
    captured: Dict[str, Any] = {}

    async def _fake_select(*args: Any, **kwargs: Any) -> SelectionOutcome:
        return SelectionOutcome(
            ok=True, selected=["proto.a"] * DECK_SIZE, total=DECK_SIZE
        )

    monkeypatch.setattr(deck_module, "select_prototypes_for_actor", _fake_select)
    monkeypatch.setattr(
        deck_module,
        "materialize_candidate",
        lambda prototype_id, source: _candidate(prototype_id),
    )

    async def _fake_design(*args: Any, **kwargs: Any) -> DesignOutcome:
        captured.update(kwargs)
        total = len(kwargs["candidates"])
        return DesignOutcome(ok=True, designed=total, total=total, affixes=0)

    monkeypatch.setattr(deck_module, "design_cards_for_actor", _fake_design)

    cards, is_fallback = await system._build_cards(_actor(), [_entry("proto.a")], [])

    assert is_fallback is False
    assert len(cards) == DECK_SIZE
    assert captured["actor_motif"] == _MOTIF


#######################################################################################################################################
async def test_assembled_deck_keeps_motif_component(
    system: AssembleDungeonDeckSystem, monkeypatch: pytest.MonkeyPatch
) -> None:
    """挂牌库时合并 components：MotifComponent 不能被 DeckComponent 覆盖掉。"""
    actor = _actor()

    async def _fake_build(*args: Any, **kwargs: Any) -> Tuple[List[Card], bool]:
        return [Card(name="牌", description="", source=actor.name)], False

    monkeypatch.setattr(system, "_build_cards", _fake_build)

    ok = await system._assemble_actor_deck(actor, [], [])

    assert ok is True
    assert DeckComponent.__name__ in actor.components
    assert actor.components[MotifComponent.__name__]["motif"] == _MOTIF
