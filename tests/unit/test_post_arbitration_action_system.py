"""PostArbitrationActionSystem 单元测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    DungeonComponent,
    HandComponent,
    PostArbitrationAction,
    StageComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models import Card, StatusEffect, PhaseType, AIMessage
from src.ai_rpg.systems.post_arbitration_action_system import (
    ActorPostArbitrationDirective,
    CardInjectStrategy,
    PostArbitrationActionSystem,
)
from src.ai_rpg.systems.arbitration_prompt_builders import fmt_duration
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor_entity(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "test_sheet", "test_stage")
    entity.add(StatusEffectsComponent, name, [])
    entity.add(HandComponent, name, [], 1)
    return entity


def _make_stage_entity(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(StageComponent, name, "test_stage_sheet")
    entity.add(DungeonComponent, name)
    entity.add(PostArbitrationAction, name, "行动者")
    return entity


def _make_effect(
    name: str = "燃烧",
    description: str = "持续灼烧",
    duration: int = 2,
    phase: PhaseType = PhaseType.ARBITRATION,
    speed: int = 0,
    defense: int = 0,
) -> StatusEffect:
    return StatusEffect(
        name=name,
        description=description,
        duration=duration,
        phase=phase,
        speed=speed,
        defense=defense,
    )


def _make_card(name: str = "斩击", damage_dealt: int = 3) -> Card:
    return Card(name=name, description="挥砍", damage_dealt=damage_dealt)


def _make_mock_chat_client(
    name: str,
    response_json: str,
    *,
    prompt: str = "full prompt",
    compressed_prompt: str = "compressed prompt",
) -> MagicMock:
    client = MagicMock()
    client.name = name
    client.prompt = prompt
    client.compressed_prompt = compressed_prompt
    client.response_content = response_json
    client.response_ai_message = AIMessage(content=response_json)
    return client


def _build_response_json(
    target: str,
    effects: Optional[List[StatusEffect]] = None,
    cards: Optional[List[Card]] = None,
) -> str:
    """构建标准的 StagePostArbitrationResponse JSON 字符串。"""
    import json

    directives: List[Dict[str, object]] = []
    if effects or cards:
        d: Dict[str, object] = {"target": target}
        d["add_effects"] = [
            {
                "name": e.name,
                "description": e.description,
                "duration": e.duration,
                "phase": str(e.phase),
                "speed": e.speed,
            }
            for e in (effects or [])
        ]
        d["inject_cards"] = [
            {
                "name": c.name,
                "description": c.description,
                "damage_dealt": c.damage_dealt,
                "hit_count": c.hit_count,
                "target_type": str(c.target_type),
            }
            for c in (cards or [])
        ]
        directives.append(d)

    return json.dumps({"per_actor": directives})


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
def system(mock_game: MagicMock) -> PostArbitrationActionSystem:
    return PostArbitrationActionSystem(
        mock_game,
        strategy=CardInjectStrategy.APPEND,
        use_compressed_prompt=True,
    )


@pytest.fixture()
def system_random_insert(mock_game: MagicMock) -> PostArbitrationActionSystem:
    return PostArbitrationActionSystem(
        mock_game,
        strategy=CardInjectStrategy.RANDOM_INSERT,
        use_compressed_prompt=True,
    )


# ---------------------------------------------------------------------------
# Phase 1 — 纯函数
# ---------------------------------------------------------------------------


class TestFmtDuration:
    """`_fmt_duration` 的单元测试。"""

    def test_minus_one_returns_永久(self) -> None:
        assert fmt_duration(-1) == "永久"

    def test_positive_returns_remaining_n_rounds(self) -> None:
        assert fmt_duration(3) == "剩余3回合"
        assert fmt_duration(1) == "剩余1回合"

    def test_zero_edge_case(self) -> None:
        assert fmt_duration(0) == "剩余0回合"


# ---------------------------------------------------------------------------
# Phase 2 — 系统方法
# ---------------------------------------------------------------------------


class TestApplyStatusEffects:
    """`PostArbitrationActionSystem._apply_status_effects` 的单元测试。"""

    def test_new_effect_appended(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "暗黑地下城")
        target = _make_actor_entity(context, "英雄")
        directive = ActorPostArbitrationDirective(
            target="英雄", add_effects=[_make_effect("燃烧")]
        )

        system._apply_status_effects(stage, target, directive)

        effects = target.get(StatusEffectsComponent).status_effects
        assert len(effects) == 1
        assert effects[0].name == "燃烧"

    def test_duplicate_name_skipped(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "英雄")
        # 预先放一个同名效果
        target.get(StatusEffectsComponent).status_effects.append(_make_effect("燃烧"))

        directive = ActorPostArbitrationDirective(
            target="英雄", add_effects=[_make_effect("燃烧")]
        )
        system._apply_status_effects(stage, target, directive)

        # 依然只有 1 个
        assert len(target.get(StatusEffectsComponent).status_effects) == 1

    def test_source_set_to_stage_entity_name(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "石牢")
        target = _make_actor_entity(context, "战士")
        directive = ActorPostArbitrationDirective(
            target="战士", add_effects=[_make_effect("中毒")]
        )

        system._apply_status_effects(stage, target, directive)

        effects = target.get(StatusEffectsComponent).status_effects
        assert effects[0].source == "石牢"

    def test_multiple_effects_partial_dedup(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        """2 个 effect，1 个同名已存在 → 只追加 1 个。"""
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "法师")
        target.get(StatusEffectsComponent).status_effects.append(_make_effect("燃烧"))

        directive = ActorPostArbitrationDirective(
            target="法师",
            add_effects=[_make_effect("燃烧"), _make_effect("冰冻")],
        )
        system._apply_status_effects(stage, target, directive)

        names = [e.name for e in target.get(StatusEffectsComponent).status_effects]
        assert names.count("燃烧") == 1
        assert "冰冻" in names

    def test_speed_99_clamped_by_field_validator(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        """speed=99 构造 StatusEffect 时 field_validator 应归一化为 1。"""
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "盗贼")
        # field_validator 在 StatusEffect 构造时触发
        directive = ActorPostArbitrationDirective(
            target="盗贼",
            add_effects=[_make_effect("疾风", speed=99)],
        )
        system._apply_status_effects(stage, target, directive)

        effects = target.get(StatusEffectsComponent).status_effects
        assert effects[0].speed == 1

    def test_defense_positive_stored(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        """defense=3 构造 StatusEffect 时应原值保留（无 clamp）。"""
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "骑士")
        directive = ActorPostArbitrationDirective(
            target="骑士",
            add_effects=[_make_effect("沙土护身", defense=3)],
        )
        system._apply_status_effects(stage, target, directive)

        effects = target.get(StatusEffectsComponent).status_effects
        assert effects[0].defense == 3

    def test_defense_negative_stored(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        """defense=-2 构造 StatusEffect 时应原值保留（无 clamp）。"""
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "弓手")
        directive = ActorPostArbitrationDirective(
            target="弓手",
            add_effects=[_make_effect("破甲", defense=-2)],
        )
        system._apply_status_effects(stage, target, directive)

        effects = target.get(StatusEffectsComponent).status_effects
        assert effects[0].defense == -2


class TestInjectCards:
    """`PostArbitrationActionSystem._inject_cards` 的单元测试。"""

    def test_card_appended_to_hand(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "英雄")
        directive = ActorPostArbitrationDirective(
            target="英雄", inject_cards=[_make_card("斩击")]
        )

        system._inject_cards(stage, target, directive)

        cards = target.get(HandComponent).cards
        assert len(cards) == 1
        assert cards[0].name == "斩击"

    def test_duplicate_card_skipped(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "英雄")
        target.get(HandComponent).cards = [_make_card("斩击")]

        directive = ActorPostArbitrationDirective(
            target="英雄", inject_cards=[_make_card("斩击")]
        )
        system._inject_cards(stage, target, directive)

        assert len(target.get(HandComponent).cards) == 1

    def test_source_set_to_stage_name(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "熔岩洞穴")
        target = _make_actor_entity(context, "弓手")
        directive = ActorPostArbitrationDirective(
            target="弓手", inject_cards=[_make_card("火石投掷")]
        )

        system._inject_cards(stage, target, directive)

        cards = target.get(HandComponent).cards
        assert cards[0].source == "熔岩洞穴"

    def test_no_new_cards_hand_unchanged(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "法师")
        existing = _make_card("火球")
        target.get(HandComponent).cards = [existing]

        directive = ActorPostArbitrationDirective(
            target="法师", inject_cards=[_make_card("火球")]
        )
        system._inject_cards(stage, target, directive)

        assert len(target.get(HandComponent).cards) == 1

    def test_random_insert_card_appears_in_hand(
        self,
        context: Context,
        mock_game: MagicMock,
        system_random_insert: PostArbitrationActionSystem,
    ) -> None:
        """RANDOM_INSERT 策略下，卡牌应出现在 hand.cards 中（不验证具体位置）。"""
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "游侠")
        # 预置若干手牌
        target.get(HandComponent).cards = [_make_card(f"牌{i}") for i in range(4)]

        directive = ActorPostArbitrationDirective(
            target="游侠", inject_cards=[_make_card("奇袭")]
        )
        system_random_insert._inject_cards(stage, target, directive)

        names = [c.name for c in target.get(HandComponent).cards]
        assert "奇袭" in names
        assert len(names) == 5


class TestApplyResponse:
    """`PostArbitrationActionSystem._apply_response` 的单元测试。"""

    def test_valid_response_applies_effects_and_cards(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "英雄")
        mock_game.get_entity_by_name.return_value = target

        response_json = _build_response_json(
            "英雄",
            effects=[_make_effect("燃烧")],
            cards=[_make_card("碎石投掷")],
        )
        client = _make_mock_chat_client("地下城", response_json)

        system._apply_response(stage, client)

        assert len(target.get(StatusEffectsComponent).status_effects) == 1
        assert len(target.get(HandComponent).cards) == 1

    def test_empty_per_actor_no_change(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "战士")
        mock_game.get_entity_by_name.return_value = target

        client = _make_mock_chat_client("地下城", '{"per_actor": []}')
        system._apply_response(stage, client)

        assert target.get(StatusEffectsComponent).status_effects == []
        assert target.get(HandComponent).cards == []

    def test_unknown_target_logs_error_no_crash(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        """target 不存在时应 log error 并不抛出。"""
        stage = _make_stage_entity(context, "地下城")
        mock_game.get_entity_by_name.return_value = None

        response_json = _build_response_json(
            "不存在的角色", effects=[_make_effect("燃烧")]
        )
        client = _make_mock_chat_client("地下城", response_json)

        # 不应抛出异常
        system._apply_response(stage, client)

    def test_calls_add_human_message_once(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "法师")
        mock_game.get_entity_by_name.return_value = target

        client = _make_mock_chat_client("地下城", '{"per_actor": []}')
        system._apply_response(stage, client)

        mock_game.add_human_message.assert_called_once()

    def test_calls_add_ai_message_once(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "法师")
        mock_game.get_entity_by_name.return_value = target

        client = _make_mock_chat_client("地下城", '{"per_actor": []}')
        system._apply_response(stage, client)

        mock_game.add_ai_message.assert_called_once()

    def test_compressed_prompt_forwarded_to_add_human_message(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        """use_compressed_prompt=True 时，compressed_prompt 应传入 add_human_message。"""
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "牧师")
        mock_game.get_entity_by_name.return_value = target

        client = _make_mock_chat_client(
            "地下城",
            '{"per_actor": []}',
            prompt="full prompt",
            compressed_prompt="compressed",
        )
        system._apply_response(stage, client)

        call_kwargs = mock_game.add_human_message.call_args[1]
        assert call_kwargs.get("message_content") == "compressed"


# ---------------------------------------------------------------------------
# Phase 3 — 异步 react()
# ---------------------------------------------------------------------------


class TestPostArbitrationActionSystemReact:
    """PostArbitrationActionSystem.react() 的异步测试。"""

    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        """战斗未进行中时，batch_chat 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = False
        stage = _make_stage_entity(context, "地下城")

        with patch(
            "src.ai_rpg.systems.post_arbitration_action_system.DeepSeekClient.batch_chat",
            new_callable=AsyncMock,
        ) as mock_batch:
            await system.react([stage])
            mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_stage_called_for_stage_entity(
        self,
        context: Context,
        mock_game: MagicMock,
        system: PostArbitrationActionSystem,
    ) -> None:
        """stage entity → _process_stage 应被调用一次。"""
        mock_game.current_dungeon.is_ongoing = True
        stage = _make_stage_entity(context, "地下城")

        with patch.object(
            system, "_process_stage", new_callable=AsyncMock
        ) as mock_process:
            await system.react([stage])
            mock_process.assert_called_once_with(stage)
