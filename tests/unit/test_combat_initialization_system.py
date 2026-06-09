"""CombatInitializationSystem 单元测试。"""

from typing import List, Set
from unittest.mock import MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    AddStatusEffectsAction,
    AppearanceComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    MonsterComponent,
    PartyMemberComponent,
    StageDescriptionComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.models.stats import CharacterStats
from src.ai_rpg.systems.combat_initialization_system import (
    CombatInitializationSystem,
    OtherActorInfo,
    _format_other_actors_info,
    _generate_combat_init_prompt,
    _generate_init_status_effects_task_hint,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor_entity(
    context: Context,
    name: str,
    *,
    is_ally: bool = False,
    is_monster: bool = False,
    appearance: str = "普通外观",
) -> Entity:
    """创建带外观和阵营标记的参战角色实体。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(AppearanceComponent, name, "base_body", appearance)
    if is_ally:
        entity.add(PartyMemberComponent, name, "test_dungeon")
    if is_monster:
        entity.add(MonsterComponent, name)
    return entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    """提供真实 ECS Context，保证组件操作（add/replace/has/get）正确生效。"""
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    """MagicMock TCGGame，避免初始化重量级 TCGGame 依赖。

    accumulate_status_effects_action 的 side_effect 模拟真实合并逻辑，
    以便单元测试仍能断言实体上的 AddStatusEffectsAction 组件状态。
    """
    game = MagicMock(spec=TCGGame)

    def _accumulate(entity: Entity, task_hints: List[str]) -> None:
        existing_hints: List[str] = (
            entity.get(AddStatusEffectsAction).task_hints
            if entity.has(AddStatusEffectsAction)
            else []
        )
        entity.replace(AddStatusEffectsAction, entity.name, existing_hints + task_hints)

    game.accumulate_status_effects_action.side_effect = _accumulate
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> CombatInitializationSystem:
    return CombatInitializationSystem(mock_game)


# ---------------------------------------------------------------------------
# Phase 1 — 纯函数测试
# ---------------------------------------------------------------------------


class TestFormatOtherActorsInfo:
    """_format_other_actors_info 的单元测试。"""

    def test_empty_list_returns_none_string(self) -> None:
        """空列表应返回 '无'。"""
        assert _format_other_actors_info([]) == "无"

    def test_single_item_formats_as_markdown(self) -> None:
        """单条目应格式化为 '- **名称**（阵营）: 外观' 的 Markdown 格式。"""
        info = OtherActorInfo(
            actor_name="英雄", other_name="哥布林", appearance="绿色皮肤", camp="敌方"
        )
        result = _format_other_actors_info([info])
        assert "**哥布林**" in result
        assert "敌方" in result
        assert "绿色皮肤" in result

    def test_multiple_items_joined_by_double_newline(self) -> None:
        """多条目应以 '\\n\\n' 分隔。"""
        infos = [
            OtherActorInfo(
                actor_name="A", other_name="B", appearance="外观B", camp="友方"
            ),
            OtherActorInfo(
                actor_name="A", other_name="C", appearance="外观C", camp="敌方"
            ),
        ]
        result = _format_other_actors_info(infos)
        assert "\n\n" in result
        assert "**B**" in result
        assert "**C**" in result


class TestGenerateCombatInitPrompt:
    """_generate_combat_init_prompt 的单元测试。"""

    def _make_stats(
        self, hp: int = 15, max_hp: int = 20, attack: int = 8, defense: int = 3
    ) -> CharacterStats:
        return CharacterStats(hp=hp, max_hp=max_hp, attack=attack, defense=defense)

    def test_contains_stage_name(self) -> None:
        result = _generate_combat_init_prompt(
            "暗黑地下城", "昏暗的石牢", [], self._make_stats()
        )
        assert "暗黑地下城" in result

    def test_contains_stage_description(self) -> None:
        result = _generate_combat_init_prompt(
            "地下城", "到处都是岩浆", [], self._make_stats()
        )
        assert "到处都是岩浆" in result

    def test_contains_actor_stats(self) -> None:
        stats = self._make_stats(hp=10, max_hp=25, attack=7, defense=4)
        result = _generate_combat_init_prompt("地下城", "描述", [], stats)
        assert "10/25" in result
        assert "7" in result
        assert "4" in result

    def test_no_other_actors_shows_none_string(self) -> None:
        result = _generate_combat_init_prompt("地下城", "描述", [], self._make_stats())
        assert "无" in result

    def test_other_actors_included_in_output(self) -> None:
        info = OtherActorInfo(
            actor_name="英雄", other_name="骷髅兵", appearance="骨架", camp="敌方"
        )
        result = _generate_combat_init_prompt(
            "地下城", "描述", [info], self._make_stats()
        )
        assert "骷髅兵" in result


class TestGenerateInitStatusEffectsTaskHint:
    """_generate_init_status_effects_task_hint 的单元测试。"""

    def test_returns_non_empty_string(self) -> None:
        result = _generate_init_status_effects_task_hint()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(h, str) and len(h) > 0 for h in result)

    def test_mentions_combat_initialization(self) -> None:
        result = _generate_init_status_effects_task_hint()
        assert any("战斗初始化" in h for h in result)


# ---------------------------------------------------------------------------
# Phase 2 — 系统方法测试
# ---------------------------------------------------------------------------


class TestDetermineCapRelationship:
    """_determine_camp_relationship 的单元测试。"""

    def test_both_allies_returns_friendly(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """双方均为 PartyMember → '友方'。"""
        a = _make_actor_entity(context, "英雄", is_ally=True)
        b = _make_actor_entity(context, "同伴", is_ally=True)
        assert system._determine_camp_relationship(a, b) == "友方"

    def test_both_monsters_returns_friendly(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """双方均为 Monster → '友方'。"""
        a = _make_actor_entity(context, "哥布林", is_monster=True)
        b = _make_actor_entity(context, "骷髅", is_monster=True)
        assert system._determine_camp_relationship(a, b) == "友方"

    def test_ally_vs_monster_returns_enemy(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """友方 vs 怪物 → '敌方'。"""
        ally = _make_actor_entity(context, "英雄", is_ally=True)
        monster = _make_actor_entity(context, "哥布林", is_monster=True)
        assert system._determine_camp_relationship(ally, monster) == "敌方"

    def test_monster_vs_ally_returns_enemy(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """怪物 vs 友方 → '敌方'。"""
        monster = _make_actor_entity(context, "哥布林", is_monster=True)
        ally = _make_actor_entity(context, "英雄", is_ally=True)
        assert system._determine_camp_relationship(monster, ally) == "敌方"


class TestGenerateOtherActorsInfo:
    """_generate_other_actors_info 的单元测试。"""

    def test_single_actor_returns_empty_list(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """只有自身时应返回空列表。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        result = system._generate_other_actors_info(actor, {actor})
        assert result == []

    def test_two_actors_returns_one_entry(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """两个角色时，对方信息应出现在返回列表中。"""
        ally = _make_actor_entity(context, "英雄", is_ally=True, appearance="银甲骑士")
        monster = _make_actor_entity(
            context, "哥布林", is_monster=True, appearance="绿色皮肤"
        )
        result = system._generate_other_actors_info(ally, {ally, monster})
        assert len(result) == 1
        entry = result[0]
        assert entry.other_name == "哥布林"
        assert entry.appearance == "绿色皮肤"
        assert entry.camp == "敌方"

    def test_entry_actor_name_matches_self(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """返回条目中的 actor_name 应为当前角色自身。"""
        ally = _make_actor_entity(context, "英雄", is_ally=True)
        monster = _make_actor_entity(context, "哥布林", is_monster=True)
        result = system._generate_other_actors_info(ally, {ally, monster})
        assert result[0].actor_name == "英雄"

    def test_three_actors_returns_two_entries(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """三个角色时，当前角色应获得两条其他角色信息。"""
        hero = _make_actor_entity(context, "英雄", is_ally=True)
        goblin = _make_actor_entity(context, "哥布林", is_monster=True)
        troll = _make_actor_entity(context, "巨魔", is_monster=True)
        result = system._generate_other_actors_info(hero, {hero, goblin, troll})
        assert len(result) == 2
        other_names = {r.other_name for r in result}
        assert other_names == {"哥布林", "巨魔"}


class TestInitializeActorStatusEffects:
    """_initialize_actor_status_effects 的单元测试。"""

    def test_adds_empty_status_effects_component(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """执行后角色应持有空 StatusEffectsComponent。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        system._initialize_actor_status_effects({actor})
        assert actor.has(StatusEffectsComponent)
        assert actor.get(StatusEffectsComponent).status_effects == []

    def test_adds_add_status_effects_action(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """执行后角色应持有 AddStatusEffectsAction。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        system._initialize_actor_status_effects({actor})
        assert actor.has(AddStatusEffectsAction)

    def test_action_task_hint_is_non_empty(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """AddStatusEffectsAction 的 task_hints 应为非空字符串列表。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        system._initialize_actor_status_effects({actor})
        action = actor.get(AddStatusEffectsAction)
        assert isinstance(action.task_hints, list)
        assert len(action.task_hints) > 0
        assert all(isinstance(h, str) and len(h) > 0 for h in action.task_hints)

    def test_multiple_actors_all_initialized(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """多个角色应全部获得 StatusEffectsComponent 和 AddStatusEffectsAction。"""
        actors = {
            _make_actor_entity(context, "英雄", is_ally=True),
            _make_actor_entity(context, "哥布林", is_monster=True),
        }
        system._initialize_actor_status_effects(actors)
        for actor in actors:
            assert actor.has(StatusEffectsComponent)
            assert actor.has(AddStatusEffectsAction)

    def test_raises_if_actor_has_non_empty_status_effects(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """若角色已有非空 status_effects，应触发 AssertionError。"""
        from src.ai_rpg.models import StatusEffect, PhaseType

        actor = _make_actor_entity(context, "英雄", is_ally=True)
        existing_effect = StatusEffect(
            name="中毒",
            description="每回合损失 HP",
            phase=PhaseType.ARBITRATION,
            duration=2,
        )
        actor.add(StatusEffectsComponent, "英雄", [existing_effect])

        with pytest.raises(AssertionError):
            system._initialize_actor_status_effects({actor})


class TestInitializeActorPiles:
    """_initialize_actor_piles 的单元测试。"""

    def test_adds_all_three_pile_components(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """执行后角色应持有全部三个空 Pile 组件。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        system._initialize_actor_piles({actor})
        assert actor.has(DrawPileComponent)
        assert actor.has(DiscardPileComponent)
        assert actor.has(ExhaustPileComponent)

    def test_all_piles_are_empty(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """初始化后三个 Pile 均应为空列表。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        system._initialize_actor_piles({actor})
        assert actor.get(DrawPileComponent).cards == []
        assert actor.get(DiscardPileComponent).cards == []
        assert actor.get(ExhaustPileComponent).cards == []

    def test_multiple_actors_all_initialized(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """多个角色应全部获得三个 Pile 组件。"""
        actors = {
            _make_actor_entity(context, "英雄", is_ally=True),
            _make_actor_entity(context, "哥布林", is_monster=True),
        }
        system._initialize_actor_piles(actors)
        for actor in actors:
            assert actor.has(DrawPileComponent)
            assert actor.has(DiscardPileComponent)
            assert actor.has(ExhaustPileComponent)

    def test_raises_if_draw_pile_already_exists(
        self, context: Context, system: CombatInitializationSystem
    ) -> None:
        """若角色已有 DrawPileComponent，应触发 AssertionError（防重复初始化）。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        actor.add(DrawPileComponent, "英雄", [])
        with pytest.raises(AssertionError):
            system._initialize_actor_piles({actor})


class TestAddContextForAllActors:
    """_add_context_for_all_actors 的单元测试。"""

    def _setup(
        self,
        mock_game: MagicMock,
        context: Context,
        actors: Set[Entity],
    ) -> None:
        """为 mock_game 配置 compute_character_stats 返回值，指向真实实体集合。"""
        mock_game.compute_character_stats.return_value = CharacterStats()

    def test_add_human_message_called_once_per_actor(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """每个角色应恰好调用一次 add_human_message。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        self._setup(mock_game, context, {actor})

        system._add_context_for_all_actors({actor}, "迷雾森林", "阴暗的树林")

        mock_game.add_human_message.assert_called_once()

    def test_add_ai_message_called_once_per_actor(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """每个角色应恰好调用一次 add_ai_message。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        self._setup(mock_game, context, {actor})

        system._add_context_for_all_actors({actor}, "迷雾森林", "阴暗的树林")

        mock_game.add_ai_message.assert_called_once()

    def test_ai_message_content_is_correct(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """注入的 AI 消息内容应为固定的战斗就绪回应。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        self._setup(mock_game, context, {actor})

        system._add_context_for_all_actors({actor}, "迷雾森林", "阴暗的树林")

        _, kwargs = mock_game.add_ai_message.call_args
        ai_msg: AIMessage = kwargs["ai_message"]
        assert ai_msg.content == "已感知战场环境，进入战斗准备状态。"

    def test_human_message_contains_stage_name(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """注入的 Human 消息应包含 stage_name。"""
        actor = _make_actor_entity(context, "英雄", is_ally=True)
        self._setup(mock_game, context, {actor})

        system._add_context_for_all_actors({actor}, "血色竞技场", "充满杀意的沙场")

        _, kwargs = mock_game.add_human_message.call_args
        assert "血色竞技场" in kwargs["message_content"]

    def test_called_for_each_of_multiple_actors(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """多个角色时 add_human_message / add_ai_message 各自调用次数等于角色数量。"""
        actors = {
            _make_actor_entity(context, "英雄", is_ally=True),
            _make_actor_entity(context, "哥布林", is_monster=True),
        }
        self._setup(mock_game, context, actors)

        system._add_context_for_all_actors(actors, "迷雾森林", "阴暗的树林")

        assert mock_game.add_human_message.call_count == 2
        assert mock_game.add_ai_message.call_count == 2


# ---------------------------------------------------------------------------
# Phase 3 — execute() 编排逻辑测试
# ---------------------------------------------------------------------------


class TestExecute:
    """CombatInitializationSystem.execute() 的单元测试。"""

    def _configure_mock_game_for_execute(
        self,
        mock_game: MagicMock,
        context: Context,
        *,
        is_initializing: bool = True,
        is_player_in_dungeon_stage: bool = True,
        is_ongoing: bool = True,
    ) -> tuple[Entity, Entity]:
        """为 execute() 配置 mock_game 所需的所有返回值。返回 (player_entity, stage_entity)。"""
        stage_entity = context.create_entity()
        stage_entity._name = "测试场景"
        stage_entity.add(StageDescriptionComponent, "测试场景", "阴暗潮湿的石牢")

        player_entity = _make_actor_entity(context, "英雄", is_ally=True)

        actor_entity = _make_actor_entity(context, "哥布林", is_monster=True)

        mock_game.current_dungeon.is_initializing = is_initializing
        mock_game.current_dungeon.current_rounds = []
        mock_game.current_dungeon.is_ongoing = is_ongoing
        mock_game.is_player_in_dungeon_stage = is_player_in_dungeon_stage
        mock_game.get_player_entity.return_value = player_entity
        mock_game.resolve_stage_entity.return_value = stage_entity
        mock_game.get_alive_actors_in_stage.return_value = {player_entity, actor_entity}
        mock_game.compute_character_stats.return_value = CharacterStats()

        return player_entity, stage_entity

    @pytest.mark.asyncio
    async def test_skips_when_not_initializing(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """当 is_initializing 为 False 时，应直接返回，不调用任何下游方法。"""
        mock_game.current_dungeon.is_initializing = False

        await system.execute()

        mock_game.get_player_entity.assert_not_called()
        mock_game.get_alive_actors_in_stage.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_transition_to_ongoing(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """正常执行时应调用 transition_to_ongoing() 一次。"""
        self._configure_mock_game_for_execute(mock_game, context)

        with (
            patch.object(system, "_add_context_for_all_actors"),
            patch.object(system, "_initialize_actor_status_effects"),
        ):
            await system.execute()

        mock_game.current_dungeon.transition_to_ongoing.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegates_context_injection(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """execute() 应调用 _add_context_for_all_actors。"""
        self._configure_mock_game_for_execute(mock_game, context)

        with (
            patch.object(system, "_add_context_for_all_actors") as mock_inject,
            patch.object(system, "_initialize_actor_status_effects"),
        ):
            await system.execute()

        mock_inject.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegates_status_effect_init(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """execute() 应调用 _initialize_actor_status_effects。"""
        self._configure_mock_game_for_execute(mock_game, context)

        with (
            patch.object(system, "_add_context_for_all_actors"),
            patch.object(system, "_initialize_actor_piles"),
            patch.object(system, "_initialize_actor_status_effects") as mock_init,
        ):
            await system.execute()

        mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_delegates_pile_init(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """execute() 应调用 _initialize_actor_piles，在上下文注入之前。"""
        self._configure_mock_game_for_execute(mock_game, context)

        with (
            patch.object(system, "_add_context_for_all_actors"),
            patch.object(system, "_initialize_actor_piles") as mock_pile_init,
            patch.object(system, "_initialize_actor_status_effects"),
        ):
            await system.execute()

        mock_pile_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_injection_called_before_transition(
        self, context: Context, mock_game: MagicMock, system: CombatInitializationSystem
    ) -> None:
        """战场上下文注入应在状态转换之前发生（顺序验证）。"""
        call_order: List[str] = []

        self._configure_mock_game_for_execute(mock_game, context)
        mock_game.current_dungeon.transition_to_ongoing.side_effect = (
            lambda: call_order.append("transition")
        )

        with (
            patch.object(
                system,
                "_add_context_for_all_actors",
                side_effect=lambda *a, **kw: call_order.append("context_inject"),
            ),
            patch.object(system, "_initialize_actor_status_effects"),
        ):
            await system.execute()

        assert call_order.index("context_inject") < call_order.index("transition")
