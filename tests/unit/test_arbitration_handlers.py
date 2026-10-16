"""仲裁 `resolve_*` handler 的定点验证：数值经纯函数落到 HP，并产出同源日志段。

重点覆盖 E2E 里没有的路径：治疗回血、吸血封顶、反伤；并验证目标恒为持有者。
handler 核心已收敛到 `arbitration_common`；此处经 `turn_end` 的薄包装验证（含持有者目标约束）。
"""

from typing import Dict, List
from unittest.mock import MagicMock

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    Card,
    CharacterStats,
    CharacterStatsComponent,
    HandComponent,
    TargetType,
)
from ai_rpg.systems.arbitration_common import (
    ArbitrationContext,
)
from ai_rpg.systems.turn_end_arbitration_system import (
    _handle_resolve_damage,
    _handle_resolve_effect,
)


def _make_actor(
    context: Context, name: str, hp: int, max_hp: int, hand: List[Card]
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "dungeon")
    entity.add(CharacterStatsComponent, name, CharacterStats(hp=hp, max_hp=max_hp))
    entity.add(HandComponent, name, hand)
    return entity


def _make_game(entities: Dict[str, Entity]) -> MagicMock:
    game = MagicMock(spec=DBGGame)
    game.get_actor_entity.side_effect = lambda name: entities.get(name)
    return game


def _block_card(block: int) -> Card:
    return Card(
        name="盾",
        description="盾",
        block=block,
        self_target=True,
        target_type=TargetType.SINGLE,
    )


class TestResolveDamageHandler:
    def test_damage_subtracts_total_block(self) -> None:
        context = Context()
        hero = _make_actor(context, "英雄", hp=10, max_hp=10, hand=[_block_card(4)])
        ctx = ArbitrationContext()

        segment = _handle_resolve_damage(
            _make_game({"英雄": hero}), ctx, "英雄", "英雄", base_damage=5, hits=1
        )

        assert ctx.hp_changes["英雄"] == 9
        assert "5×1−4×1=每击1 ×1击=1" in segment
        assert "HP:英雄 10→9" in segment


class TestResolveEffectHandler:
    def test_heal_holder_raises_hp(self) -> None:
        """回合结束的受效结算目标恒为持有者本人。"""
        context = Context()
        ally = _make_actor(context, "队友", hp=4, max_hp=10, hand=[])
        ctx = ArbitrationContext()

        segment = _handle_resolve_effect(
            _make_game({"队友": ally}),
            ctx,
            "队友",
            "队友",
            base=5,
            hits=1,
            heal_mult=0.5,
            rationale="治疗术：回复 damage 的一半",
        )

        assert ctx.hp_changes["队友"] == 7  # 治疗 = round(5×0.5) = 3
        assert "治疗5×0.5=3/击 ×1击=3" in segment
        assert "HP:队友 4→7" in segment
        assert "（治疗术：回复 damage 的一半）" in segment

    def test_lifesteal_clamps_to_max_hp(self) -> None:
        context = Context()
        hero = _make_actor(context, "英雄", hp=9, max_hp=10, hand=[])
        ctx = ArbitrationContext()

        _handle_resolve_effect(
            _make_game({"英雄": hero}),
            ctx,
            "英雄",
            "英雄",
            base=5,
            hits=1,
            lifesteal_mult=1,
        )

        assert ctx.hp_changes["英雄"] == 10  # 封顶

    def test_reflect_lowers_hp_per_hit(self) -> None:
        context = Context()
        hero = _make_actor(context, "英雄", hp=10, max_hp=10, hand=[])
        ctx = ArbitrationContext()

        segment = _handle_resolve_effect(
            _make_game({"英雄": hero}),
            ctx,
            "英雄",
            "英雄",
            base=3,
            hits=2,
            reflect_mult=1,
        )

        assert ctx.hp_changes["英雄"] == 4  # 3×2=6
        assert "反伤3×1=3/击 ×2击=6 = 净扣减6" in segment

    def test_missing_entity_returns_error_without_change(self) -> None:
        context = Context()
        ctx = ArbitrationContext()

        segment = _handle_resolve_effect(
            _make_game({}), ctx, "幽灵", "幽灵", base=5, hits=1, heal_mult=1
        )

        assert "错误" in segment
        assert ctx.hp_changes == {}

    def test_damage_non_holder_target_is_rejected(self) -> None:
        """回合结束词缀不能指向非持有者。"""
        context = Context()
        hero = _make_actor(context, "英雄", hp=10, max_hp=10, hand=[])
        other = _make_actor(context, "怪物", hp=10, max_hp=10, hand=[])
        ctx = ArbitrationContext()

        segment = _handle_resolve_damage(
            _make_game({"英雄": hero, "怪物": other}),
            ctx,
            "英雄",
            "怪物",
            base_damage=5,
            hits=1,
        )

        assert "错误" in segment
        assert ctx.hp_changes == {}

    def test_effect_non_holder_target_is_rejected(self) -> None:
        context = Context()
        hero = _make_actor(context, "英雄", hp=10, max_hp=10, hand=[])
        other = _make_actor(context, "怪物", hp=10, max_hp=10, hand=[])
        ctx = ArbitrationContext()

        segment = _handle_resolve_effect(
            _make_game({"英雄": hero, "怪物": other}),
            ctx,
            "英雄",
            "怪物",
            base=5,
            hits=1,
            heal_mult=1,
        )

        assert "错误" in segment
        assert ctx.hp_changes == {}
