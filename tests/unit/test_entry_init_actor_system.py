"""EntryInitActorSystem 单元测试。"""

from unittest.mock import MagicMock

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.entitas.matcher import Matcher
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    AppearanceComponent,
    CharacterStatsComponent,
    GenerateDeckAction,
    MonsterComponent,
    PartyMemberComponent,
)
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.systems.entry_init_actor_system import (
    EntryInitActorSystem,
    OtherActorInfo,
    _build_entry_init_prompt,
    _build_other_actors_info,
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
    entity.add(ActorComponent, name, "")
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
def system(mock_game: MagicMock) -> EntryInitActorSystem:
    return EntryInitActorSystem(mock_game)


# ---------------------------------------------------------------------------
# _build_other_actors_info
# ---------------------------------------------------------------------------


def test_format_other_actors_info_empty() -> None:
    assert _build_other_actors_info([]) == "无"


def test_format_other_actors_info_contains_name_camp_appearance() -> None:
    info = OtherActorInfo(other_name="游侠", appearance="披着绿色斗篷", camp="友方")
    result = _build_other_actors_info([info])
    assert "游侠" in result
    assert "友方" in result
    assert "披着绿色斗篷" in result


# ---------------------------------------------------------------------------
# _build_entry_init_prompt
# ---------------------------------------------------------------------------


def test_build_entry_init_prompt_contains_key_fields() -> None:
    stats = CharacterStats(hp=8, max_hp=20, attack=6, defense=4)
    result = _build_entry_init_prompt(
        stage_name="入口石室",
        stage_description="潮湿阴冷的洞口",
        other_actors_info=[],
        actor_stats=stats,
    )
    assert "入口石室" in result
    assert "潮湿阴冷的洞口" in result
    assert "8/20" in result
    assert "6" in result  # attack
    assert "4" in result  # defense


# ---------------------------------------------------------------------------
# _add_context
# ---------------------------------------------------------------------------


def test_add_context_injects_human_and_ai_messages(
    context: Context, mock_game: MagicMock, system: EntryInitActorSystem
) -> None:
    actor_a = _make_actor(context, "勇者", is_ally=True)
    actor_b = _make_actor(context, "游侠", is_ally=True)

    mock_game.filter_messages.return_value = []

    system._add_context(
        actor_entities={actor_a, actor_b},
        stage_name="入口石室",
        stage_description="潮湿阴冷的洞口",
    )

    assert mock_game.add_human_message.call_count == 2
    assert mock_game.add_ai_message.call_count == 2

    # 每条 human 消息都携带入口场景标记
    for call in mock_game.add_human_message.call_args_list:
        human_message = call.kwargs["human_message"]
        assert human_message.content != ""
        assert getattr(human_message, "entry_initialization", None) == "入口石室"


def test_add_context_skips_already_injected_actor(
    context: Context, mock_game: MagicMock, system: EntryInitActorSystem
) -> None:
    actor = _make_actor(context, "勇者", is_ally=True)

    # 已有同场景标记，应跳过注入
    mock_game.filter_messages.return_value = [object()]

    system._add_context(
        actor_entities={actor},
        stage_name="入口石室",
        stage_description="潮湿阴冷的洞口",
    )

    mock_game.add_human_message.assert_not_called()
    mock_game.add_ai_message.assert_not_called()


# ---------------------------------------------------------------------------
# _add_generate_deck_actions
# ---------------------------------------------------------------------------


def test_add_generate_deck_actions_adds_action_to_party_and_monsters(
    context: Context, mock_game: MagicMock, system: EntryInitActorSystem
) -> None:
    ally = _make_actor(context, "勇者", is_ally=True)
    monster = _make_actor(context, "哥布林", is_monster=True)

    party_group = MagicMock()
    party_group.entities = {ally}
    monster_group = MagicMock()
    monster_group.entities = {monster}

    def fake_get_group(matcher: Matcher) -> MagicMock:
        if matcher.all_of == (PartyMemberComponent,):
            return party_group
        if matcher.all_of == (MonsterComponent,):
            return monster_group
        raise AssertionError(f"unexpected matcher: {matcher}")

    mock_game.get_group.side_effect = fake_get_group

    system._add_generate_deck_actions()

    assert ally.has(GenerateDeckAction)
    assert monster.has(GenerateDeckAction)
