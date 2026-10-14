"""CombatRoundStartSystem 行动顺序（speed 策略）单元测试。"""

from unittest.mock import MagicMock

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    CharacterStatsComponent,
    IdentityComponent,
    RoundStatsComponent,
)
from ai_rpg.models.character_stats import CharacterStats
from ai_rpg.systems.combat_round_start_system import (
    ActionOrderStrategy,
    CombatRoundStartSystem,
)


def _make_actor(
    context: Context,
    name: str,
    *,
    speed: int = 0,
    creation_order: int = 0,
    energy: int = 2,
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "")
    entity.add(IdentityComponent, name, creation_order, f"id-{name}")
    entity.add(CharacterStatsComponent, name, CharacterStats(speed=speed))
    entity.add(RoundStatsComponent, name, energy)
    return entity


def _system() -> CombatRoundStartSystem:
    return CombatRoundStartSystem(MagicMock(spec=DBGGame), ActionOrderStrategy.SPEED)


def test_speed_orders_descending() -> None:
    context = Context()
    slow = _make_actor(context, "slow", speed=1, creation_order=1)
    fast = _make_actor(context, "fast", speed=9, creation_order=2)
    mid = _make_actor(context, "mid", speed=5, creation_order=3)

    ordered = _system()._sorted_actors_by_speed({slow, fast, mid})

    assert [e.name for e in ordered] == ["fast", "mid", "slow"]


def test_speed_tie_breaks_by_creation_order() -> None:
    context = Context()
    later = _make_actor(context, "later", speed=3, creation_order=20)
    earlier = _make_actor(context, "earlier", speed=3, creation_order=10)

    ordered = _system()._sorted_actors_by_speed({later, earlier})

    assert [e.name for e in ordered] == ["earlier", "later"]


def test_zero_energy_actors_are_excluded() -> None:
    context = Context()
    active = _make_actor(context, "active", speed=1, energy=2)
    exhausted = _make_actor(context, "exhausted", speed=99, energy=0)

    ordered = _system()._sorted_actors_by_speed({active, exhausted})

    assert [e.name for e in ordered] == ["active"]
