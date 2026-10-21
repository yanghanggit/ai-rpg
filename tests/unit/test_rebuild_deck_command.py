"""`rebuild_deck_in_dungeon` 单测：按名字重做怪物牌库并改写副本文件。

设计会话在模块边界被替换；只测「找对怪物 / 规格照给 / 保留锚点 / 失败不写文件」。
"""

import json
from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock

import pytest

from ai_rpg.dbg_game_agent import cards as cards_module
from ai_rpg.dbg_game_agent.cards import find_dungeon_actor, rebuild_deck_in_dungeon
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    Actor,
    ActorType,
    Card,
    CharacterStats,
    CombatRoom,
    Dungeon,
    MotifComponent,
    Stage,
    StageType,
)
from ai_rpg.systems.card_common import Candidate, DesignOutcome

_MOTIF = "**母题**: 泥下的等待\n**意象**: 湿泥、干草"


def _dungeon() -> Dungeon:
    actor = Actor(
        name="怪物.泥行者",
        type=ActorType.MONSTER,
        profile="扮演设定",
        base_body="外观",
        system_message="# 怪物.泥行者",
        character_stats=CharacterStats(),
        components={MotifComponent.__name__: {"name": "怪物.泥行者", "motif": _MOTIF}},
    )
    stage = Stage(
        name="房间.泥径",
        type=StageType.DUNGEON,
        profile="泥径",
        system_message="# 房间.泥径",
        actors=[actor],
    )
    return Dungeon(name="副本.试作", profile="设定", rooms=[CombatRoom(stage=stage)])


def _candidate(prototype_id: str) -> Candidate:
    return Candidate(
        card=Card(name=f"设计后的{prototype_id}", description="", source="怪物.泥行者"),
        archetype="",
        archetype_subtype="",
        summary="",
        design="",
    )


@pytest.fixture()
def dungeon_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把 .dungeons 指向 tmp_path，并写入一份副本文件。"""
    monkeypatch.setattr(cards_module, "DUNGEONS_DIR", tmp_path)
    path = tmp_path / "副本.试作.json"
    path.write_text(_dungeon().model_dump_json(indent=4), encoding="utf-8")
    return path


def _patch_design(
    monkeypatch: pytest.MonkeyPatch, *, ok: bool = True, designed: int | None = None
) -> None:
    monkeypatch.setattr(
        cards_module,
        "materialize_candidate",
        lambda prototype_id, source: _candidate(prototype_id),
    )

    async def _fake_design(*args: Any, **kwargs: Any) -> DesignOutcome:
        total = len(kwargs["candidates"])
        done = total if designed is None else designed
        return DesignOutcome(ok=ok, designed=done if ok else 0, total=total, affixes=0)

    monkeypatch.setattr(cards_module, "design_cards_for_actor", _fake_design)


#######################################################################################################################################
def test_find_dungeon_actor_lists_available_names() -> None:
    dungeon = _dungeon()

    assert find_dungeon_actor(dungeon, "怪物.泥行者").name == "怪物.泥行者"

    with pytest.raises(ValueError, match="怪物.泥行者"):
        find_dungeon_actor(dungeon, "怪物.不存在")


#######################################################################################################################################
async def test_rebuild_deck_rewrites_file_and_keeps_motif(
    dungeon_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """按规格重做牌库：写回文件、保留艺术锚点、source 归怪物。"""
    _patch_design(monkeypatch)
    spec = ["proto.a", "proto.b", "proto.c", "proto.d", "proto.e"]

    cards = await rebuild_deck_in_dungeon(
        MagicMock(spec=DBGGame),
        dungeon_name="副本.试作",
        actor_name="怪物.泥行者",
        prototype_ids=spec,
    )

    assert [card.name for card in cards] == [f"设计后的{pid}" for pid in spec]

    saved = json.loads(dungeon_file.read_text(encoding="utf-8"))
    actor = saved["rooms"][0]["stage"]["actors"][0]
    assert [card["name"] for card in actor["components"]["DeckComponent"]["cards"]] == [
        f"设计后的{pid}" for pid in spec
    ]
    assert all(
        card["source"] == "怪物.泥行者"
        for card in actor["components"]["DeckComponent"]["cards"]
    )
    assert actor["components"][MotifComponent.__name__]["motif"] == _MOTIF


async def test_rebuild_deck_failure_leaves_file_untouched(
    dungeon_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """设计未全部落地时抛错且不改写文件（不拿半成品覆盖已有牌库）。"""
    _patch_design(monkeypatch, ok=False)
    before = dungeon_file.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="设计未完成"):
        await rebuild_deck_in_dungeon(
            MagicMock(spec=DBGGame),
            dungeon_name="副本.试作",
            actor_name="怪物.泥行者",
            prototype_ids=["proto.a"] * 5,
        )

    assert dungeon_file.read_text(encoding="utf-8") == before


async def test_rebuild_deck_unknown_actor_fails_before_design(
    dungeon_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_design(monkeypatch)
    before = dungeon_file.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="没有角色"):
        await rebuild_deck_in_dungeon(
            MagicMock(spec=DBGGame),
            dungeon_name="副本.试作",
            actor_name="怪物.不存在",
            prototype_ids=list(["proto.a"] * 5),
        )

    assert dungeon_file.read_text(encoding="utf-8") == before


async def test_rebuild_deck_requires_prototypes(
    dungeon_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError, match="至少需要一个原型"):
        await rebuild_deck_in_dungeon(
            MagicMock(spec=DBGGame),
            dungeon_name="副本.试作",
            actor_name="怪物.泥行者",
            prototype_ids=[],
        )


#######################################################################################################################################
def _dungeon_with_deck(names: List[str]) -> Dungeon:
    from ai_rpg.models import Card, DeckComponent

    dungeon = _dungeon()
    actor = dungeon.rooms[0].stage.actors[0]
    actor.components = {
        **actor.components,
        DeckComponent.__name__: DeckComponent(
            name=actor.name,
            cards=[
                Card(name=name, description="", source=actor.name) for name in names
            ],
        ).model_dump(),
    }
    return dungeon


def test_resolve_replacement_indices_by_name_and_position() -> None:
    from ai_rpg.dbg_game_agent.cards import resolve_replacement_indices
    from ai_rpg.models import Card

    existing = [Card(name=name, description="") for name in ("甲", "乙", "乙", "丁")]

    assert resolve_replacement_indices(existing, ["甲", "4"]) == [0, 3]
    assert resolve_replacement_indices(existing, ["2"]) == [1]

    with pytest.raises(ValueError, match="没有「丙」"):
        resolve_replacement_indices(existing, ["丙"])
    with pytest.raises(ValueError, match="改用序号"):
        resolve_replacement_indices(existing, ["乙"])  # 重名 → 歧义
    with pytest.raises(ValueError, match="超出范围"):
        resolve_replacement_indices(existing, ["9"])
    with pytest.raises(ValueError, match="指定了两次"):
        resolve_replacement_indices(existing, ["1", "1"])


async def test_rebuild_deck_replaces_single_card_and_keeps_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """定点替换：只换指定那张，其余牌与顺序原样保留，牌库张数不变。"""
    monkeypatch.setattr(cards_module, "DUNGEONS_DIR", tmp_path)
    (tmp_path / "副本.试作.json").write_text(
        _dungeon_with_deck(["甲", "乙", "丙", "丁", "戊"]).model_dump_json(indent=4),
        encoding="utf-8",
    )
    _patch_design(monkeypatch)

    cards = await rebuild_deck_in_dungeon(
        MagicMock(spec=DBGGame),
        dungeon_name="副本.试作",
        actor_name="怪物.泥行者",
        prototype_ids=["proto.summon"],
        replace=["丙"],
    )

    assert [card.name for card in cards] == [
        "甲",
        "乙",
        "设计后的proto.summon",
        "丁",
        "戊",
    ]


async def test_rebuild_deck_replaces_by_position(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cards_module, "DUNGEONS_DIR", tmp_path)
    (tmp_path / "副本.试作.json").write_text(
        _dungeon_with_deck(["甲", "乙", "丙", "丁", "戊"]).model_dump_json(indent=4),
        encoding="utf-8",
    )
    _patch_design(monkeypatch)

    cards = await rebuild_deck_in_dungeon(
        MagicMock(spec=DBGGame),
        dungeon_name="副本.试作",
        actor_name="怪物.泥行者",
        prototype_ids=["proto.summon", "proto.burst"],
        replace=["5", "1"],
    )

    assert [card.name for card in cards] == [
        "设计后的proto.burst",
        "乙",
        "丙",
        "丁",
        "设计后的proto.summon",
    ]


async def test_rebuild_deck_rejects_unpaired_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cards_module, "DUNGEONS_DIR", tmp_path)
    (tmp_path / "副本.试作.json").write_text(
        _dungeon_with_deck(["甲", "乙", "丙", "丁", "戊"]).model_dump_json(indent=4),
        encoding="utf-8",
    )
    _patch_design(monkeypatch)
    before = (tmp_path / "副本.试作.json").read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="一一配对"):
        await rebuild_deck_in_dungeon(
            MagicMock(spec=DBGGame),
            dungeon_name="副本.试作",
            actor_name="怪物.泥行者",
            prototype_ids=["proto.summon"],
            replace=["甲", "乙"],
        )

    assert (tmp_path / "副本.试作.json").read_text(encoding="utf-8") == before


async def test_full_rebuild_accepts_arbitrary_deck_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """整副重建的张数 = 给定原型数：游戏默认张数只是默认路径的值，不是约束。"""
    monkeypatch.setattr(cards_module, "DUNGEONS_DIR", tmp_path)
    (tmp_path / "副本.试作.json").write_text(
        _dungeon_with_deck(["甲", "乙", "丙", "丁", "戊"]).model_dump_json(indent=4),
        encoding="utf-8",
    )
    _patch_design(monkeypatch)

    cards = await rebuild_deck_in_dungeon(
        MagicMock(spec=DBGGame),
        dungeon_name="副本.试作",
        actor_name="怪物.泥行者",
        prototype_ids=["proto.a", "proto.b", "proto.c"],
    )

    assert [card.name for card in cards] == [
        "设计后的proto.a",
        "设计后的proto.b",
        "设计后的proto.c",
    ]
