"""CombatInitializationSystem 单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    AddStatusEffectsAction,
    AIMessage,
    AppearanceComponent,
    CharacterStatsComponent,
    DiscardPileComponent,
    DrawPileComponent,
    DungeonComponent,
    ExhaustPileComponent,
    MonsterComponent,
    PartyMemberComponent,
    StageComponent,
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


def _make_stage_entity(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(StageComponent, name, "test_stage_sheet")
    entity.add(DungeonComponent, name)
    return entity


def _make_mock_chat_client(response_json: str) -> MagicMock:
    client = MagicMock()
    client.prompt = "full prompt"
    client.compressed_prompt = "compressed prompt"
    client.response_content = response_json
    client.response_ai_message = AIMessage(content=response_json)
    client.chat = AsyncMock()
    return client


def _configure_lookup(mock_game: MagicMock, *entities: Entity) -> None:
    """配置 mock_game.get_entity_by_name 按名称返回对应实体，未匹配时返回 None。"""
    lookup = {e.name: e for e in entities}
    mock_game.get_entity_by_name.side_effect = lambda name: lookup.get(name)


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
# _initialize_piles_and_status_effects
# ---------------------------------------------------------------------------


def test_initialize_piles_and_status_effects_adds_all_piles(
    context: Context, system: CombatInitializationSystem
) -> None:
    actor = _make_actor(context, "勇者", is_ally=True)
    system._initialize_piles_and_status_effects({actor})

    assert actor.has(DrawPileComponent)
    assert actor.has(DiscardPileComponent)
    assert actor.has(ExhaustPileComponent)
    assert actor.get(DrawPileComponent).cards == []


def test_initialize_piles_and_status_effects_adds_empty_status_effects(
    context: Context, system: CombatInitializationSystem
) -> None:
    actor = _make_actor(context, "勇者", is_ally=True)
    system._initialize_piles_and_status_effects({actor})

    assert actor.has(StatusEffectsComponent)
    assert actor.get(StatusEffectsComponent).status_effects == []


# ---------------------------------------------------------------------------
# _evaluate_combat_init_status_effects
# ---------------------------------------------------------------------------


class TestEvaluateCombatInitStatusEffects:
    """`CombatInitializationSystem._evaluate_combat_init_status_effects` 的单元测试。"""

    @pytest.mark.asyncio
    async def test_non_empty_task_hints_accumulates_add_status_effects_action(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitializationSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client(
            '{"task_hints": {"勇者": ["[场景] 浓烟弥漫，可致眼盲"]}}'
        )

        with patch(
            "src.ai_rpg.systems.combat_initialization_system.DeepSeekClient",
            return_value=client,
        ):
            await system._evaluate_combat_init_status_effects(
                stage_entity=stage,
                actor_entities={actor},
                stage_name="地下城",
                stage_description="浓烟弥漫的地下城",
            )

        assert actor.has(AddStatusEffectsAction)
        assert actor.get(AddStatusEffectsAction).task_hints == [
            "[场景] 浓烟弥漫，可致眼盲"
        ]

    @pytest.mark.asyncio
    async def test_empty_task_hints_no_action_attached(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitializationSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client('{"task_hints": {}}')

        with patch(
            "src.ai_rpg.systems.combat_initialization_system.DeepSeekClient",
            return_value=client,
        ):
            await system._evaluate_combat_init_status_effects(
                stage_entity=stage,
                actor_entities={actor},
                stage_name="地下城",
                stage_description="平静的地下城",
            )

        assert not actor.has(AddStatusEffectsAction)

    @pytest.mark.asyncio
    async def test_unknown_actor_name_handled_gracefully(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitializationSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_lookup(mock_game, stage)  # 注意：不注册 actor，模拟未知角色
        client = _make_mock_chat_client(
            '{"task_hints": {"勇者": ["[场景] 浓烟弥漫，可致眼盲"]}}'
        )

        with patch(
            "src.ai_rpg.systems.combat_initialization_system.DeepSeekClient",
            return_value=client,
        ):
            # 不应抛出异常
            await system._evaluate_combat_init_status_effects(
                stage_entity=stage,
                actor_entities={actor},
                stage_name="地下城",
                stage_description="浓烟弥漫的地下城",
            )

        assert not actor.has(AddStatusEffectsAction)

    @pytest.mark.asyncio
    async def test_malformed_response_handled_gracefully(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitializationSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client("not a json")

        with patch(
            "src.ai_rpg.systems.combat_initialization_system.DeepSeekClient",
            return_value=client,
        ):
            await system._evaluate_combat_init_status_effects(
                stage_entity=stage,
                actor_entities={actor},
                stage_name="地下城",
                stage_description="平静的地下城",
            )

        assert not actor.has(AddStatusEffectsAction)

    @pytest.mark.asyncio
    async def test_none_response_ai_message_handled_gracefully(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitializationSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client("")
        client.response_ai_message = None

        with patch(
            "src.ai_rpg.systems.combat_initialization_system.DeepSeekClient",
            return_value=client,
        ):
            await system._evaluate_combat_init_status_effects(
                stage_entity=stage,
                actor_entities={actor},
                stage_name="地下城",
                stage_description="平静的地下城",
            )

        assert not actor.has(AddStatusEffectsAction)

    @pytest.mark.asyncio
    async def test_chat_exception_handled_gracefully(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitializationSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client("")
        client.chat = AsyncMock(side_effect=RuntimeError("boom"))

        with patch(
            "src.ai_rpg.systems.combat_initialization_system.DeepSeekClient",
            return_value=client,
        ):
            await system._evaluate_combat_init_status_effects(
                stage_entity=stage,
                actor_entities={actor},
                stage_name="地下城",
                stage_description="平静的地下城",
            )

        assert not actor.has(AddStatusEffectsAction)
