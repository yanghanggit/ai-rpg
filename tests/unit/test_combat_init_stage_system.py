"""CombatInitStageSystem 单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    AddStatusEffectsAction,
    AffixTrigger,
    AIMessage,
    AppearanceComponent,
    CharacterStatsComponent,
    DungeonComponent,
    MonsterComponent,
    PartyMemberComponent,
    StageComponent,
    StageDescriptionComponent,
)
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.systems.combat_init_stage_system import CombatInitStageSystem


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


def _make_stage_entity(
    context: Context, name: str, *, narrative: str = "平静的地下城"
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(StageComponent, name, "test_stage_sheet")
    entity.add(DungeonComponent, name)
    entity.add(StageDescriptionComponent, name, narrative)
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


def _configure_execute_prerequisites(
    mock_game: MagicMock, stage: Entity, player_entity: Entity
) -> None:
    """配置 execute() 中场景状态效果判定之前的前置流程所需的 mock（状态门禁/实体解析），
    以便测试可以直接调用 execute() 覆盖已内联的场景状态效果判定逻辑。"""
    mock_game.current_combat_room.combat.is_initializing = True
    mock_game.current_combat_room.combat.is_ongoing = True
    mock_game.get_player_entity.return_value = player_entity
    mock_game.resolve_stage_entity.return_value = stage


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
def system(mock_game: MagicMock) -> CombatInitStageSystem:
    return CombatInitStageSystem(mock_game)


# ---------------------------------------------------------------------------
# execute() — 场景状态效果判定（原 _evaluate_combat_init_status_effects 已内联）
# ---------------------------------------------------------------------------


class TestExecuteCombatInitStatusEffects:
    """`CombatInitStageSystem.execute()` 中场景状态效果判定部分的单元测试。"""

    @pytest.mark.asyncio
    async def test_non_empty_task_hints_accumulates_add_status_effects_action(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitStageSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城", narrative="浓烟弥漫的地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_execute_prerequisites(mock_game, stage, actor)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client(
            '{"task_hints": {"勇者": ["[场景] 浓烟弥漫，可致眼盲"]}}'
        )

        with (
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.DeepSeekClient",
                return_value=client,
            ),
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.get_alive_actors_in_stage",
                return_value={actor},
            ),
        ):
            await system.execute()

        assert actor.has(AddStatusEffectsAction)
        assert actor.get(AddStatusEffectsAction).affixes == [
            AffixTrigger(source="战斗初始化场景", affix="[场景] 浓烟弥漫，可致眼盲")
        ]

    @pytest.mark.asyncio
    async def test_empty_task_hints_no_action_attached(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitStageSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_execute_prerequisites(mock_game, stage, actor)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client('{"task_hints": {}}')

        with (
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.DeepSeekClient",
                return_value=client,
            ),
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.get_alive_actors_in_stage",
                return_value={actor},
            ),
        ):
            await system.execute()

        assert not actor.has(AddStatusEffectsAction)

    @pytest.mark.asyncio
    async def test_unknown_actor_name_handled_gracefully(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitStageSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城", narrative="浓烟弥漫的地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_execute_prerequisites(mock_game, stage, actor)
        _configure_lookup(mock_game, stage)  # 注意：不注册 actor，模拟未知角色
        client = _make_mock_chat_client(
            '{"task_hints": {"勇者": ["[场景] 浓烟弥漫，可致眼盲"]}}'
        )

        with (
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.DeepSeekClient",
                return_value=client,
            ),
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.get_alive_actors_in_stage",
                return_value={actor},
            ),
        ):
            # 不应抛出异常
            await system.execute()

        assert not actor.has(AddStatusEffectsAction)

    @pytest.mark.asyncio
    async def test_malformed_response_handled_gracefully(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitStageSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_execute_prerequisites(mock_game, stage, actor)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client("not a json")

        with (
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.DeepSeekClient",
                return_value=client,
            ),
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.get_alive_actors_in_stage",
                return_value={actor},
            ),
        ):
            await system.execute()

        assert not actor.has(AddStatusEffectsAction)

    @pytest.mark.asyncio
    async def test_none_response_ai_message_handled_gracefully(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitStageSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_execute_prerequisites(mock_game, stage, actor)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client("")
        client.response_ai_message = None

        with (
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.DeepSeekClient",
                return_value=client,
            ),
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.get_alive_actors_in_stage",
                return_value={actor},
            ),
        ):
            await system.execute()

        assert not actor.has(AddStatusEffectsAction)

    @pytest.mark.asyncio
    async def test_chat_exception_handled_gracefully(
        self,
        context: Context,
        mock_game: MagicMock,
        system: CombatInitStageSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        actor = _make_actor(context, "勇者", is_ally=True)
        _configure_execute_prerequisites(mock_game, stage, actor)
        _configure_lookup(mock_game, stage, actor)
        client = _make_mock_chat_client("")
        client.chat = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.DeepSeekClient",
                return_value=client,
            ),
            patch(
                "src.ai_rpg.systems.combat_init_stage_system.get_alive_actors_in_stage",
                return_value={actor},
            ),
        ):
            await system.execute()

        assert not actor.has(AddStatusEffectsAction)
