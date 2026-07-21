"""InjectCardsActionSystem 单元测试。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    DungeonComponent,
    DiscardPileComponent,
    PlayCardsAction,
    StageComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models import Card, AIMessage
from src.ai_rpg.systems.inject_cards_action_system import (
    ActorPostArbitrationDirective,
    InjectCardsActionSystem,
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
    entity.add(DiscardPileComponent, name, [])
    return entity


def _make_stage_entity(context: Context, name: str) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(StageComponent, name, "test_stage_sheet")
    entity.add(DungeonComponent, name)
    return entity


def _make_actor_with_play_cards_action(context: Context, name: str) -> Entity:
    entity = _make_actor_entity(context, name)
    entity.add(
        PlayCardsAction,
        name,
        _make_card("斩击"),
        [name],
    )
    return entity


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


def _configure_lookup(mock_game: MagicMock, *entities: Entity) -> None:
    """配置 mock_game.get_entity_by_name 按名称返回对应实体，未匹配时返回 None。"""
    lookup = {e.name: e for e in entities}
    mock_game.get_entity_by_name.side_effect = lambda name: lookup.get(name)


def _build_response_json(
    target: str,
    cards: Optional[List[Card]] = None,
) -> str:
    """构建标准的 StagePostArbitrationResponse JSON 字符串。"""
    import json

    directives: List[Dict[str, object]] = []
    if cards:
        d: Dict[str, object] = {"target": target}
        d["inject_cards"] = [
            {
                "name": c.name,
                "description": c.description,
                "damage_dealt": c.damage_dealt,
                "hit_count": c.hit_count,
                "target_type": str(c.target_type),
            }
            for c in cards
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
def system(mock_game: MagicMock) -> InjectCardsActionSystem:
    return InjectCardsActionSystem(
        mock_game,
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


class TestInjectCards:
    """`InjectCardsActionSystem._inject_cards` 的单元测试。"""

    def test_card_appended_to_discard_pile(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "英雄")
        directive = ActorPostArbitrationDirective(
            target="英雄", inject_cards=[_make_card("斩击")]
        )

        system._inject_cards(stage, target, directive.inject_cards)

        cards = target.get(DiscardPileComponent).cards
        assert len(cards) == 1
        assert cards[0].name == "斩击"

    def test_duplicate_card_skipped(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "英雄")
        target.get(DiscardPileComponent).cards = [_make_card("斩击")]

        directive = ActorPostArbitrationDirective(
            target="英雄", inject_cards=[_make_card("斩击")]
        )
        system._inject_cards(stage, target, directive.inject_cards)

        assert len(target.get(DiscardPileComponent).cards) == 1

    def test_source_set_to_stage_name(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "熔岩洞穴")
        target = _make_actor_entity(context, "弓手")
        directive = ActorPostArbitrationDirective(
            target="弓手", inject_cards=[_make_card("火石投掷")]
        )

        system._inject_cards(stage, target, directive.inject_cards)

        cards = target.get(DiscardPileComponent).cards
        assert cards[0].source == "熔岩洞穴"

    def test_no_new_cards_discard_pile_unchanged(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "法师")
        existing = _make_card("火球")
        target.get(DiscardPileComponent).cards = [existing]

        directive = ActorPostArbitrationDirective(
            target="法师", inject_cards=[_make_card("火球")]
        )
        system._inject_cards(stage, target, directive.inject_cards)

        assert len(target.get(DiscardPileComponent).cards) == 1


class TestApplyResponse:
    """`InjectCardsActionSystem._apply_response` 的单元测试。"""

    def test_valid_response_applies_effects_and_cards(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "英雄")
        _configure_lookup(mock_game, stage, target)

        response_json = _build_response_json(
            "英雄",
            cards=[_make_card("碎石投掷")],
        )
        client = _make_mock_chat_client("地下城", response_json)

        system._apply_response(client)

        assert len(target.get(DiscardPileComponent).cards) == 1

    def test_empty_per_actor_no_change(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "战士")
        _configure_lookup(mock_game, stage, target)

        client = _make_mock_chat_client("地下城", '{"per_actor": []}')
        system._apply_response(client)

        assert target.get(StatusEffectsComponent).status_effects == []
        assert target.get(DiscardPileComponent).cards == []

    def test_unknown_target_logs_error_no_crash(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        """target 不存在时应 log error 并不抛出。"""
        stage = _make_stage_entity(context, "地下城")
        _configure_lookup(mock_game, stage)

        response_json = _build_response_json(
            "不存在的角色", cards=[_make_card("碎石投掷")]
        )
        client = _make_mock_chat_client("地下城", response_json)

        # 不应抛出异常
        system._apply_response(client)

    def test_writes_context_messages_once(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        """human/ai 消息应各写入 stage entity 对话历史一次。"""
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "法师")
        _configure_lookup(mock_game, stage, target)

        client = _make_mock_chat_client("地下城", '{"per_actor": []}')
        system._apply_response(client)

        mock_game.add_human_message.assert_called_once()
        mock_game.add_ai_message.assert_called_once()

    def test_compressed_prompt_forwarded_to_add_human_message(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        """use_compressed_prompt=True 时，compressed_prompt 应传入 add_human_message。"""
        stage = _make_stage_entity(context, "地下城")
        target = _make_actor_entity(context, "牧师")
        _configure_lookup(mock_game, stage, target)

        client = _make_mock_chat_client(
            "地下城",
            '{"per_actor": []}',
            prompt="full prompt",
            compressed_prompt="compressed",
        )
        system._apply_response(client)

        call_kwargs = mock_game.add_human_message.call_args[1]
        assert call_kwargs.get("human_message").content == "compressed"


# ---------------------------------------------------------------------------
# Phase 3 — 异步 react()
# ---------------------------------------------------------------------------


class TestInjectCardsActionSystemReact:
    """InjectCardsActionSystem.react() 的异步测试。"""

    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        """战斗未进行中时，_process_actor_action 不应被调用。"""
        mock_game.current_combat_room.combat.is_ongoing = False
        actor = _make_actor_with_play_cards_action(context, "英雄")

        with patch.object(
            system, "_process_actor_action", new_callable=AsyncMock
        ) as mock_process:
            await system.react([actor])
            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_actor_action_called_for_actor_entity(
        self,
        context: Context,
        mock_game: MagicMock,
        system: InjectCardsActionSystem,
    ) -> None:
        """actor entity（携带 PlayCardsAction）→ _process_actor_action 应被调用一次。"""
        mock_game.current_combat_room.combat.is_ongoing = True
        actor = _make_actor_with_play_cards_action(context, "英雄")

        with patch.object(
            system, "_process_actor_action", new_callable=AsyncMock
        ) as mock_process:
            await system.react([actor])
            mock_process.assert_called_once_with(actor)
