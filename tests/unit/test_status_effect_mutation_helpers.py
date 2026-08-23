"""状态效果增删成员函数单元测试。"""

from unittest.mock import MagicMock

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import PhaseType, StatusEffect, StatusEffectsComponent
from src.ai_rpg.systems.add_status_effects_action_system import (
    AddStatusEffectsActionSystem,
)
from src.ai_rpg.systems.combat_round_end_settlement_system import (
    CombatRoundEndSettlementSystem,
)


def _make_entity(ctx: Context, name: str) -> Entity:
    entity = ctx.create_entity()
    entity._name = name
    entity.add(StatusEffectsComponent, name, [])
    return entity


def _effect(name: str, description: str = "desc") -> StatusEffect:
    return StatusEffect(name=name, description=description, duration=3)


def _round_end_system() -> CombatRoundEndSettlementSystem:
    return CombatRoundEndSettlementSystem(MagicMock(spec=DBGGame))


def _add_system() -> AddStatusEffectsActionSystem:
    return AddStatusEffectsActionSystem(MagicMock(spec=DBGGame))


# ---------------------------------------------------------------------------
# CombatRoundEndSettlementSystem._remove_status_effects_by_name
# ---------------------------------------------------------------------------


def test_remove_by_name_removes_all_matching() -> None:
    ctx = Context()
    entity = _make_entity(ctx, "英雄")
    entity.get(StatusEffectsComponent).status_effects = [
        _effect("中毒"),
        _effect("灼烧"),
        _effect("中毒"),
    ]

    removed = _round_end_system()._remove_status_effects_by_name(entity, ["中毒"])

    names = [e.name for e in entity.get(StatusEffectsComponent).status_effects]
    assert names == ["灼烧"]
    assert [e.name for e in removed] == ["中毒", "中毒"]


def test_remove_by_name_no_match_returns_empty() -> None:
    ctx = Context()
    entity = _make_entity(ctx, "英雄")
    entity.get(StatusEffectsComponent).status_effects = [_effect("中毒")]

    removed = _round_end_system()._remove_status_effects_by_name(entity, ["不存在"])

    assert removed == []
    assert len(entity.get(StatusEffectsComponent).status_effects) == 1


# ---------------------------------------------------------------------------
# AddStatusEffectsActionSystem._upsert_status_effects
# ---------------------------------------------------------------------------


def test_upsert_same_name_overwrites_and_preserves_identity() -> None:
    ctx = Context()
    entity = _make_entity(ctx, "英雄")
    old = StatusEffect(
        name="中毒",
        description="每回合末损失 2 HP",
        duration=2,
        phase=PhaseType.ROUND_END,
        source="敌人",
        affix="毒素词缀",
    )
    entity.get(StatusEffectsComponent).status_effects = [old]

    new = StatusEffect(
        name="中毒",
        description="每回合末损失 5 HP",
        duration=4,
        phase=PhaseType.ROUND_END,
        counter=3,
        speed=-1,
        defense=-2,
        source="不应覆盖",
        affix="不应覆盖",
    )
    _add_system()._upsert_status_effects(entity, [new])

    effects = entity.get(StatusEffectsComponent).status_effects
    assert len(effects) == 1
    result = effects[0]
    # 保留身份与来源
    assert result.uuid == old.uuid
    assert result.source == "敌人"
    assert result.affix == "毒素词缀"
    # 更新数值字段
    assert result.description == "每回合末损失 5 HP"
    assert result.duration == 4
    assert result.counter == 3
    assert result.speed == -1
    assert result.defense == -2


def test_upsert_different_name_appends() -> None:
    ctx = Context()
    entity = _make_entity(ctx, "英雄")
    entity.get(StatusEffectsComponent).status_effects = [_effect("中毒")]

    _add_system()._upsert_status_effects(entity, [_effect("灼烧")])

    names = [e.name for e in entity.get(StatusEffectsComponent).status_effects]
    assert names == ["中毒", "灼烧"]
