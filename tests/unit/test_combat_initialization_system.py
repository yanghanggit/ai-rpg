"""CombatInitializationSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    AppearanceComponent,
    CharacterStatsComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    MonsterComponent,
    PartyMemberComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.systems.combat_initialization_system import (
    CombatInitializationSystem,
    OtherActorInfo,
    _format_other_actors_info,
    _generate_combat_init_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(
    context: Context,
    name: str,
    *,
    is_ally: bool = False,
    is_monster: bool = False,
    appearance: str = "普通外观",
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, f"{name}_sheet", "")
    entity.add(CharacterStatsComponent, name, CharacterStats())
    entity.add(AppearanceComponent, name, "base_body", appearance)
    if is_ally:
        entity.add(PartyMemberComponent, name)
    if is_monster:
        entity.add(MonsterComponent, name)
    return entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    return MagicMock(spec=DBGGame)


@pytest.fixture()
def system(mock_game: MagicMock) -> CombatInitializationSystem:
    return CombatInitializationSystem(mock_game)


# ---------------------------------------------------------------------------
# _format_other_actors_info
# ---------------------------------------------------------------------------


def test_format_other_actors_info_empty() -> None:
    assert _format_other_actors_info([]) == "无"


def test_format_other_actors_info_contains_name_camp_appearance() -> None:
    info = OtherActorInfo(other_name="骷髅战士", appearance="披着破烂盔甲", camp="敌方")
    result = _format_other_actors_info([info])
    assert "骷髅战士" in result
    assert "敌方" in result
    assert "披着破烂盔甲" in result


# ---------------------------------------------------------------------------
# _generate_combat_init_prompt
# ---------------------------------------------------------------------------


def test_generate_combat_init_prompt_contains_key_fields() -> None:
    stats = CharacterStats(hp=8, max_hp=20, attack=6, defense=4)
    result = _generate_combat_init_prompt(
        stage_name="地下城一层",
        stage_description="阴暗潮湿的石室",
        other_actors_info=[],
        actor_stats=stats,
    )
    assert "地下城一层" in result
    assert "阴暗潮湿的石室" in result
    assert "8/20" in result
    assert "6" in result  # attack
    assert "4" in result  # defense


# ---------------------------------------------------------------------------
# _initialize_piles
# ---------------------------------------------------------------------------


def test_initialize_piles_adds_all_three_piles(
    context: Context, system: CombatInitializationSystem
) -> None:
    actor = _make_actor(context, "勇者", is_ally=True)
    system._initialize_piles({actor})

    assert actor.has(DrawPileComponent)
    assert actor.has(DiscardPileComponent)
    assert actor.has(ExhaustPileComponent)
    assert actor.get(DrawPileComponent).cards == []


# ---------------------------------------------------------------------------
# _initialize_status_effects
# ---------------------------------------------------------------------------


def test_initialize_status_effects_adds_empty_component(
    context: Context, system: CombatInitializationSystem
) -> None:
    actor = _make_actor(context, "勇者", is_ally=True)
    system._initialize_status_effects({actor})

    assert actor.has(StatusEffectsComponent)
    assert actor.get(StatusEffectsComponent).status_effects == []
