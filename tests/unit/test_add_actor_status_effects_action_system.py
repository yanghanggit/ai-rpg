"""AddActorStatusEffectsActionSystem 单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

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
from src.ai_rpg.models.cards import StatusEffect, EffectPhase
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.systems.add_actor_status_effects_action_system import (
    AddActorStatusEffectsActionSystem,
    _generate_add_status_effects_prompt,
    _generate_compressed_add_status_effects_prompt,
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
    """创建参战角色实体，按参数装配组件。"""
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "test_sheet", "test_stage")
    if with_status_effects:
        entity.add(StatusEffectsComponent, name, [])
    if with_action:
        entity.add(AddStatusEffectsAction, name, "测试任务提示")
    if dead:
        entity.add(DeathComponent, name)
    return entity


def _make_effect(
    name: str = "燃烧",
    description: str = "持续灼烧",
    duration: int = 3,
    phase: EffectPhase = EffectPhase.ARBITRATION,
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
    """返回预设好 response_content / response_ai_message 的 MagicMock chat client。"""
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
def system(mock_game: MagicMock) -> AddActorStatusEffectsActionSystem:
    return AddActorStatusEffectsActionSystem(mock_game, use_compressed_prompt=True)


@pytest.fixture()
def system_no_compress(mock_game: MagicMock) -> AddActorStatusEffectsActionSystem:
    return AddActorStatusEffectsActionSystem(mock_game, use_compressed_prompt=False)


# ---------------------------------------------------------------------------
# Phase 1 — 纯函数
# ---------------------------------------------------------------------------


class TestGenerateCompressedAddStatusEffectsPrompt:
    """_generate_compressed_add_status_effects_prompt 的单元测试。"""

    def test_empty_effects_shows_none(self) -> None:
        result = _generate_compressed_add_status_effects_prompt([], 1, "任务", 2)
        assert "无" in result

    def test_few_effects_shows_full_description(self) -> None:
        effects = [
            _make_effect("中毒", "每回合扣血", duration=2),
            _make_effect("虚弱", "攻击减弱", duration=1),
        ]
        result = _generate_compressed_add_status_effects_prompt(effects, 1, "任务", 2)
        assert "中毒" in result
        assert "每回合扣血" in result
        assert "虚弱" in result
        assert "攻击减弱" in result

    def test_many_effects_shows_name_only(self) -> None:
        effects = [_make_effect(f"效果{i}", f"描述{i}") for i in range(5)]
        result = _generate_compressed_add_status_effects_prompt(effects, 1, "任务", 2)
        assert "效果0" in result
        # 描述不应出现（超过3个时仅展示名称）
        assert "描述0" not in result

    def test_contains_round_number(self) -> None:
        result = _generate_compressed_add_status_effects_prompt([], 7, "任务", 2)
        assert "7" in result

    def test_contains_task_hint(self) -> None:
        result = _generate_compressed_add_status_effects_prompt(
            [], 1, "这是特殊任务提示", 2
        )
        assert "这是特殊任务提示" in result

    def test_permanent_duration_shows_永久(self) -> None:
        effects = [_make_effect("诅咒", "永久削弱", duration=-1)]
        result = _generate_compressed_add_status_effects_prompt(effects, 1, "任务", 2)
        assert "永久" in result


class TestGenerateAddStatusEffectsPrompt:
    """_generate_add_status_effects_prompt 的单元测试。"""

    def test_contains_round_number(self) -> None:
        result = _generate_add_status_effects_prompt([], 5, "任务", 2)
        assert "5" in result

    def test_contains_task_hint(self) -> None:
        result = _generate_add_status_effects_prompt([], 1, "特定提示内容XYZ", 2)
        assert "特定提示内容XYZ" in result

    def test_phase_table_contains_draw_and_arbitration(self) -> None:
        result = _generate_add_status_effects_prompt([], 1, "任务", 2)
        assert EffectPhase.DRAW in result
        assert EffectPhase.ARBITRATION in result

    def test_speed_constraint_mentioned(self) -> None:
        result = _generate_add_status_effects_prompt([], 1, "任务", 2)
        assert "+1 / 0 / -1" in result

    def test_json_template_present(self) -> None:
        result = _generate_add_status_effects_prompt([], 1, "任务", 2)
        assert "add_effects" in result

    def test_empty_effects_shows_none(self) -> None:
        result = _generate_add_status_effects_prompt([], 1, "任务", 2)
        assert "无" in result

    def test_few_effects_shows_full_description(self) -> None:
        effects = [_make_effect("燃烧", "持续灼烧扣血", duration=2)]
        result = _generate_add_status_effects_prompt(effects, 1, "任务", 2)
        assert "燃烧" in result
        assert "持续灼烧扣血" in result

    def test_many_effects_shows_name_only(self) -> None:
        effects = [_make_effect(f"效果{i}", f"描述{i}") for i in range(5)]
        result = _generate_add_status_effects_prompt(effects, 1, "任务", 2)
        assert "效果0" in result
        assert "描述0" not in result


# ---------------------------------------------------------------------------
# Phase 2 — 系统方法
# ---------------------------------------------------------------------------


class TestProcessStatusEffectsResponse:
    """AddActorStatusEffectsActionSystem._process_status_effects_response 的单元测试。"""

    def test_valid_response_appends_effects(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "英雄", with_status_effects=True)
        response_json = '{"add_effects": [{"name": "燃烧", "description": "持续灼烧", "duration": 2, "phase": "arbitration"}]}'
        client = _make_mock_chat_client("英雄", response_json)
        mock_game.get_entity_by_name.return_value = (
            entity  # not used here, but set for safety
        )

        system._process_status_effects_response(entity, client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert len(effects) == 1
        assert effects[0].name == "燃烧"

    def test_source_set_to_entity_name(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "法师")
        response_json = '{"add_effects": [{"name": "虚弱", "description": "削弱", "duration": 1, "phase": "arbitration"}]}'
        client = _make_mock_chat_client("法师", response_json)

        system._process_status_effects_response(entity, client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert effects[0].source == "法师"

    def test_empty_add_effects_no_change(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "战士")
        response_json = '{"add_effects": []}'
        client = _make_mock_chat_client("战士", response_json)

        system._process_status_effects_response(entity, client)

        assert entity.get(StatusEffectsComponent).status_effects == []

    def test_speed_plus5_clamped_to_1(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        """LLM 返回 speed=5，field_validator 应归一化为 1。"""
        entity = _make_actor_entity(context, "刺客")
        response_json = '{"add_effects": [{"name": "疾风", "description": "加速", "duration": 2, "phase": "arbitration", "speed": 5}]}'
        client = _make_mock_chat_client("刺客", response_json)

        system._process_status_effects_response(entity, client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert effects[0].speed == 1

    def test_speed_minus3_clamped_to_minus1(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        """LLM 返回 speed=-3，field_validator 应归一化为 -1。"""
        entity = _make_actor_entity(context, "弓手")
        response_json = '{"add_effects": [{"name": "迟缓", "description": "减速", "duration": 2, "phase": "arbitration", "speed": -3}]}'
        client = _make_mock_chat_client("弓手", response_json)

        system._process_status_effects_response(entity, client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert effects[0].speed == -1

    def test_defense_positive_parsed(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        """LLM 返回 defense=2，应原值保留（无 clamp）。"""
        entity = _make_actor_entity(context, "战士")
        response_json = '{"add_effects": [{"name": "护盾", "description": "增防", "duration": 2, "phase": "arbitration", "defense": 2}]}'
        client = _make_mock_chat_client("战士", response_json)

        system._process_status_effects_response(entity, client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert effects[0].defense == 2

    def test_defense_negative_parsed(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        """LLM 返回 defense=-2（破甲），应原值保留（无 clamp）。"""
        entity = _make_actor_entity(context, "刺客")
        response_json = '{"add_effects": [{"name": "破甲", "description": "减防", "duration": 2, "phase": "arbitration", "defense": -2}]}'
        client = _make_mock_chat_client("刺客", response_json)

        system._process_status_effects_response(entity, client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert effects[0].defense == -2

    def test_defense_default_zero(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        """未提供 defense 字段时默认为 0。"""
        entity = _make_actor_entity(context, "法师")
        response_json = '{"add_effects": [{"name": "燃烧", "description": "灼烧", "duration": 2, "phase": "arbitration"}]}'
        client = _make_mock_chat_client("法师", response_json)

        system._process_status_effects_response(entity, client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert effects[0].defense == 0

    def test_invalid_json_logs_and_no_crash(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "骑士")
        client = _make_mock_chat_client("骑士", "这不是JSON")

        # 不应抛出异常
        system._process_status_effects_response(entity, client)

        # 未写入任何效果
        assert entity.get(StatusEffectsComponent).status_effects == []

    def test_calls_add_human_message_once(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "术士")
        response_json = '{"add_effects": []}'
        client = _make_mock_chat_client("术士", response_json)

        system._process_status_effects_response(entity, client)

        mock_game.add_human_message.assert_called_once()

    def test_calls_add_ai_message_once(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "祭司")
        response_json = '{"add_effects": []}'
        client = _make_mock_chat_client("祭司", response_json)

        system._process_status_effects_response(entity, client)

        mock_game.add_ai_message.assert_called_once()

    def test_compressed_prompt_passed_when_enabled(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        """use_compressed_prompt=True 时，应将 compressed_prompt 传给 add_human_message。"""
        entity = _make_actor_entity(context, "猎人")
        response_json = '{"add_effects": []}'
        client = _make_mock_chat_client(
            "猎人", response_json, prompt="full", compressed_prompt="compressed"
        )

        system._process_status_effects_response(entity, client)

        call_kwargs = mock_game.add_human_message.call_args
        assert call_kwargs is not None
        # message_content 应为 compressed_prompt
        positional_or_kw = call_kwargs[1] if call_kwargs[1] else {}
        message_content = positional_or_kw.get(
            "message_content", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
        )
        assert message_content == "compressed"

    def test_full_prompt_used_when_no_compress(
        self,
        context: Context,
        mock_game: MagicMock,
        system_no_compress: AddActorStatusEffectsActionSystem,
    ) -> None:
        """use_compressed_prompt=False 时，应将 full prompt 传给 add_human_message。"""
        entity = _make_actor_entity(context, "游侠")
        response_json = '{"add_effects": []}'
        client = _make_mock_chat_client(
            "游侠",
            response_json,
            prompt="full prompt content",
            compressed_prompt="compressed",
        )

        system_no_compress._process_status_effects_response(entity, client)

        call_kwargs = mock_game.add_human_message.call_args
        assert call_kwargs is not None
        positional_or_kw = call_kwargs[1] if call_kwargs[1] else {}
        message_content = positional_or_kw.get(
            "message_content", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
        )
        assert message_content == "full prompt content"


# ---------------------------------------------------------------------------
# Phase 3 — 异步 react()
# ---------------------------------------------------------------------------


class TestAddActorStatusEffectsActionSystemReact:
    """AddActorStatusEffectsActionSystem.react() 的异步测试。"""

    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        """战斗未进行中时，batch_chat 不应被调用。"""
        mock_game.current_dungeon.is_ongoing = False
        entity = _make_actor_entity(context, "英雄", with_action=True)

        with patch(
            "src.ai_rpg.systems.add_actor_status_effects_action_system.DeepSeekClient.batch_chat",
            new_callable=AsyncMock,
        ) as mock_batch:
            await system.react([entity])
            mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_chat_called_with_correct_count(
        self,
        context: Context,
        mock_game: MagicMock,
        system: AddActorStatusEffectsActionSystem,
    ) -> None:
        """2 个 actor → batch_chat 被调用，clients 数量 == 2。"""
        mock_game.current_dungeon.is_ongoing = True
        mock_game.current_dungeon.current_rounds = [1, 2]
        mock_game.get_agent_context.return_value = MagicMock(context=[])
        actor1 = _make_actor_entity(context, "英雄", with_action=True)
        actor2 = _make_actor_entity(context, "法师", with_action=True)

        mock_game.get_entity_by_name.side_effect = lambda name: next(
            (e for e in [actor1, actor2] if e.name == name), None
        )

        captured_clients: list[object] = []

        async def _capture_batch(clients: list[object]) -> None:
            captured_clients.extend(clients)

        with (
            patch(
                "src.ai_rpg.systems.add_actor_status_effects_action_system.DeepSeekClient.batch_chat",
                side_effect=_capture_batch,
            ),
            patch.object(system, "_process_status_effects_response"),
        ):
            await system.react([actor1, actor2])

        assert len(captured_clients) == 2

    def test_filter_rejects_dead_actor(
        self, context: Context, system: AddActorStatusEffectsActionSystem
    ) -> None:
        """带 DeathComponent 的实体应被 filter() 拒绝。"""
        entity = _make_actor_entity(
            context, "亡灵", with_status_effects=True, with_action=True, dead=True
        )
        assert system.filter(entity) is False

    def test_filter_accepts_valid_actor(
        self, context: Context, system: AddActorStatusEffectsActionSystem
    ) -> None:
        """同时持有 AddStatusEffectsAction + StatusEffectsComponent + ActorComponent 且未死亡的实体应通过 filter()。"""
        entity = _make_actor_entity(
            context, "勇士", with_status_effects=True, with_action=True, dead=False
        )
        assert system.filter(entity) is True
