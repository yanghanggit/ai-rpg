"""AddActorStatusEffectsActionSystem 单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.tcg_game import TCGGame
from src.ai_rpg.models import (
    ActorComponent,
    AddStatusEffectsAction,
    DeathComponent,
    StatusEffectsComponent,
)
from src.ai_rpg.models import StatusEffect, PhaseType
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.systems.add_status_effects_action_system import (
    AddStatusEffectsActionSystem,
)
from src.ai_rpg.systems.status_effect_prompt_builders import (
    generate_add_status_effects_prompt,
    generate_compressed_add_status_effects_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor_entity(
    context: Context,
    name: str,
    *,
    with_status_effects: bool = True,
    with_action: bool = False,
    dead: bool = False,
) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "test_sheet", "test_stage")
    if with_status_effects:
        entity.add(StatusEffectsComponent, name, [])
    if with_action:
        entity.add(AddStatusEffectsAction, name, ["测试任务提示"])
    if dead:
        entity.add(DeathComponent, name)
    return entity


def _make_effect(
    name: str = "燃烧",
    description: str = "持续灼烧",
    duration: int = 3,
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    return MagicMock(spec=TCGGame)


@pytest.fixture()
def system(mock_game: MagicMock) -> AddStatusEffectsActionSystem:
    return AddStatusEffectsActionSystem(mock_game, use_compressed_prompt=True)


@pytest.fixture()
def system_no_compress(mock_game: MagicMock) -> AddStatusEffectsActionSystem:
    return AddStatusEffectsActionSystem(mock_game, use_compressed_prompt=False)


# ---------------------------------------------------------------------------
# Phase 1 — 纯函数
# ---------------------------------------------------------------------------


class TestGenerateCompressedAddStatusEffectsPrompt:
    def test_basic_content(self) -> None:
        """空效果时包含"无"、回合数和任务提示。"""
        result = generate_compressed_add_status_effects_prompt([], 7, ["特殊任务提示"])
        assert "无" in result
        assert "7" in result
        assert "特殊任务提示" in result

    def test_few_effects_show_full_description(self) -> None:
        """不超过阈值时，名称和描述都应出现。"""
        effects = [_make_effect("中毒", "每回合扣血"), _make_effect("虚弱", "攻击减弱")]
        result = generate_compressed_add_status_effects_prompt(effects, 1, ["任务"])
        assert "中毒" in result and "每回合扣血" in result
        assert "虚弱" in result and "攻击减弱" in result

    def test_many_effects_show_name_only_and_permanent_duration(self) -> None:
        """超过阈值时只展示名称；duration=-1 应显示"永久"。"""
        effects = [_make_effect(f"效果{i}", f"描述{i}") for i in range(4)]
        effects.append(_make_effect("诅咒", "永久削弱", duration=-1))
        result = generate_compressed_add_status_effects_prompt(effects, 1, ["任务"])
        assert "效果0" in result and "描述0" not in result
        assert "永久" in result


class TestGenerateAddStatusEffectsPrompt:
    def test_output_structure(self) -> None:
        """包含回合数、任务提示、JSON 模板、phase 表格、speed 约束和"无"。"""
        result = generate_add_status_effects_prompt([], 5, ["特定提示XYZ"])
        assert "无" in result
        assert "5" in result
        assert "特定提示XYZ" in result
        assert "add_effects" in result
        assert PhaseType.DRAW in result
        assert PhaseType.ARBITRATION in result
        assert "+1 / 0 / -1" in result

    def test_few_effects_show_full_description(self) -> None:
        effects = [_make_effect("燃烧", "持续灼烧扣血")]
        result = generate_add_status_effects_prompt(effects, 1, ["任务"])
        assert "燃烧" in result and "持续灼烧扣血" in result

    def test_many_effects_show_name_only(self) -> None:
        effects = [_make_effect(f"效果{i}", f"描述{i}") for i in range(5)]
        result = generate_add_status_effects_prompt(effects, 1, ["任务"])
        assert "效果0" in result and "描述0" not in result


# ---------------------------------------------------------------------------
# Phase 2 — _process_status_effects_response
# ---------------------------------------------------------------------------


class TestProcessStatusEffectsResponse:
    def test_happy_path(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddStatusEffectsActionSystem,
    ) -> None:
        """有效响应：效果追加、source 设为实体名、human/ai message 各写入一次。"""
        entity = _make_actor_entity(context, "英雄")
        mock_game.get_entity_by_name.return_value = entity
        response_json = '{"add_effects": [{"name": "燃烧", "description": "持续灼烧", "duration": 2, "phase": "arbitration"}]}'
        client = _make_mock_chat_client("英雄", response_json)

        system._process_status_effects_response(client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert len(effects) == 1
        assert effects[0].name == "燃烧"
        assert effects[0].source == "英雄"
        mock_game.add_human_message.assert_called_once()
        mock_game.add_ai_message.assert_called_once()

    def test_empty_effects_no_change(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "战士")
        mock_game.get_entity_by_name.return_value = entity
        system._process_status_effects_response(
            _make_mock_chat_client("战士", '{"add_effects": []}')
        )
        assert entity.get(StatusEffectsComponent).status_effects == []

    def test_field_validation(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddStatusEffectsActionSystem,
    ) -> None:
        """speed 超范围归一化；defense 正负值保留原值，缺省为 0。"""
        entity = _make_actor_entity(context, "刺客")
        mock_game.get_entity_by_name.return_value = entity
        cases = [
            (
                '{"add_effects": [{"name": "疾风", "description": "加速", "duration": 2, "phase": "arbitration", "speed": 5}]}',
                "speed",
                1,
            ),
            (
                '{"add_effects": [{"name": "迟缓", "description": "减速", "duration": 2, "phase": "arbitration", "speed": -3}]}',
                "speed",
                -1,
            ),
            (
                '{"add_effects": [{"name": "护盾", "description": "增防", "duration": 2, "phase": "arbitration", "defense": 2}]}',
                "defense",
                2,
            ),
            (
                '{"add_effects": [{"name": "破甲", "description": "减防", "duration": 2, "phase": "arbitration", "defense": -2}]}',
                "defense",
                -2,
            ),
            (
                '{"add_effects": [{"name": "灼烧", "description": "灼烧", "duration": 2, "phase": "arbitration"}]}',
                "defense",
                0,
            ),
        ]
        for json_str, _, _ in cases:
            system._process_status_effects_response(
                _make_mock_chat_client("刺客", json_str)
            )
        effects = entity.get(StatusEffectsComponent).status_effects
        for i, (_, field, expected) in enumerate(cases):
            assert getattr(effects[i], field) == expected

    def test_invalid_json_no_crash(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "骑士")
        mock_game.get_entity_by_name.return_value = entity
        system._process_status_effects_response(
            _make_mock_chat_client("骑士", "不是JSON")
        )
        assert entity.get(StatusEffectsComponent).status_effects == []

    def test_compressed_prompt_mode(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddStatusEffectsActionSystem,
    ) -> None:
        """use_compressed_prompt=True 时 message_content 应为 compressed_prompt。"""
        entity = _make_actor_entity(context, "猎人")
        mock_game.get_entity_by_name.return_value = entity
        client = _make_mock_chat_client(
            "猎人", '{"add_effects": []}', prompt="full", compressed_prompt="compressed"
        )
        system._process_status_effects_response(client)
        assert (
            mock_game.add_human_message.call_args[1]["message_content"] == "compressed"
        )

    def test_full_prompt_mode(
        self,
        context: Context,
        mock_game: MagicMock,
        system_no_compress: AddStatusEffectsActionSystem,
    ) -> None:
        """use_compressed_prompt=False 时 message_content 应为 full prompt。"""
        entity = _make_actor_entity(context, "游侠")
        mock_game.get_entity_by_name.return_value = entity
        client = _make_mock_chat_client(
            "游侠",
            '{"add_effects": []}',
            prompt="full prompt content",
            compressed_prompt="compressed",
        )
        system_no_compress._process_status_effects_response(client)
        assert (
            mock_game.add_human_message.call_args[1]["message_content"]
            == "full prompt content"
        )


# ---------------------------------------------------------------------------
# Phase 3 — 异步 react()
# ---------------------------------------------------------------------------


class TestAddActorStatusEffectsActionSystemReact:
    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddStatusEffectsActionSystem,
    ) -> None:
        """战斗未进行中时，batch_chat 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = False
        entity = _make_actor_entity(context, "英雄", with_action=True)
        with patch(
            "src.ai_rpg.systems.add_status_effects_action_system.DeepSeekClient.batch_chat",
            new_callable=AsyncMock,
        ) as mock_batch:
            await system.react([entity])
            mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_chat_called_with_correct_count(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddStatusEffectsActionSystem,
    ) -> None:
        """2 个 actor → batch_chat 收到 2 个 client。"""
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = [1, 2]
        mock_game.get_agent_context.return_value = MagicMock(context=[])
        actor1 = _make_actor_entity(context, "英雄", with_action=True)
        actor2 = _make_actor_entity(context, "法师", with_action=True)
        mock_game.get_entity_by_name.side_effect = lambda name: next(
            (e for e in [actor1, actor2] if e.name == name), None
        )

        captured: List[object] = []

        async def _capture(clients: List[object]) -> None:
            captured.extend(clients)

        with (
            patch(
                "src.ai_rpg.systems.add_status_effects_action_system.DeepSeekClient.batch_chat",
                side_effect=_capture,
            ),
            patch.object(system, "_process_status_effects_response"),
        ):
            await system.react([actor1, actor2])

        assert len(captured) == 2

    def test_filter_rejects_dead_actor(
        self, context: Context, system: AddStatusEffectsActionSystem
    ) -> None:
        entity = _make_actor_entity(context, "亡灵", with_action=True, dead=True)
        assert system.filter(entity) is False

    def test_filter_accepts_valid_actor(
        self, context: Context, system: AddStatusEffectsActionSystem
    ) -> None:
        entity = _make_actor_entity(context, "勇士", with_action=True)
        assert system.filter(entity) is True


# ---------------------------------------------------------------------------
