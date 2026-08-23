"""UpdateStatusEffectsActionSystem 单元测试。"""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai_rpg.entitas.context import Context
from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    AddStatusEffectsAction,
    AffixTrigger,
    DeathComponent,
    PhaseType,
    StatusEffect,
    StatusEffectsComponent,
)
from src.ai_rpg.models.messages import AIMessage
from src.ai_rpg.systems.update_status_effects_action_system import (
    UpdateStatusEffectsActionSystem,
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
    entity.add(ActorComponent, name, "test_stage")
    if with_status_effects:
        entity.add(StatusEffectsComponent, name, [])
    if with_action:
        entity.add(
            AddStatusEffectsAction,
            name,
            [AffixTrigger(source="测试", affix="测试词缀")],
        )
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
    condensed_prompt: str = "condensed prompt",
) -> MagicMock:
    client = MagicMock()
    client.name = name
    client.full_prompt = prompt
    client.condensed_prompt = condensed_prompt
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
    return MagicMock(spec=DBGGame)


@pytest.fixture()
def system(mock_game: MagicMock) -> UpdateStatusEffectsActionSystem:
    return UpdateStatusEffectsActionSystem(mock_game, use_condensed_prompt=True)


@pytest.fixture()
def system_no_condense(mock_game: MagicMock) -> UpdateStatusEffectsActionSystem:
    return UpdateStatusEffectsActionSystem(mock_game, use_condensed_prompt=False)


class TestProcessStatusEffectsResponse:
    def test_happy_path(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        """有效响应：效果追加、source 设为实体名、affix 回填自触发词缀、human/ai message 各写入一次。"""
        entity = _make_actor_entity(context, "英雄", with_action=True)
        mock_game.get_entity_by_name.return_value = entity
        response_json = '{"add_effects": [{"name": "燃烧", "description": "持续灼烧", "duration": 2, "phase": "arbitration"}]}'
        client = _make_mock_chat_client("英雄", response_json)

        system._process_status_effects_response(client)

        effects = entity.get(StatusEffectsComponent).status_effects
        assert len(effects) == 1
        assert effects[0].name == "燃烧"
        assert effects[0].source == "英雄"
        assert effects[0].affix == "测试词缀"
        # 出牌 prompt 写入一次 + 新增效果后的状态效果通知消息写入一次，共两次
        assert mock_game.add_human_message.call_count == 2
        mock_game.add_ai_message.assert_called_once()

        notification_call = mock_game.add_human_message.call_args_list[1]
        notification_message = notification_call.kwargs["human_message"]
        assert notification_message.status_effects_notification == "英雄"
        assert "燃烧" in notification_message.content

    def test_empty_effects_no_change(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "战士", with_action=True)
        mock_game.get_entity_by_name.return_value = entity
        system._process_status_effects_response(
            _make_mock_chat_client("战士", '{"add_effects": []}')
        )
        assert entity.get(StatusEffectsComponent).status_effects == []

    def test_remove_effects_removes_by_name_and_notifies(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        """remove_effects 按名移除同名效果，并写入移除通知与状态效果通知。"""
        entity = _make_actor_entity(context, "英雄", with_action=True)
        entity.get(StatusEffectsComponent).status_effects = [
            _make_effect("中毒"),
            _make_effect("灼烧"),
            _make_effect("中毒"),
        ]
        mock_game.get_entity_by_name.return_value = entity
        system._process_status_effects_response(
            _make_mock_chat_client(
                "英雄", '{"add_effects": [], "remove_effects": ["中毒"]}'
            )
        )

        names = [e.name for e in entity.get(StatusEffectsComponent).status_effects]
        assert names == ["灼烧"]
        # prompt + 移除通知 + 状态效果通知，共 3 条 human 消息
        assert mock_game.add_human_message.call_count == 3
        remove_call = mock_game.add_human_message.call_args_list[1]
        assert "中毒" in remove_call.kwargs["human_message"].content

    def test_remove_then_add_ordering(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        """先移除后增添：同名效果被移除后再新增，最终仅保留新增结果。"""
        entity = _make_actor_entity(context, "英雄", with_action=True)
        entity.get(StatusEffectsComponent).status_effects = [
            _make_effect("中毒", description="旧"),
        ]
        mock_game.get_entity_by_name.return_value = entity
        response_json = (
            '{"remove_effects": ["中毒"], "add_effects": ['
            '{"name": "中毒", "description": "新", "duration": 2, "phase": "arbitration"}]}'
        )
        system._process_status_effects_response(
            _make_mock_chat_client("英雄", response_json)
        )

        effects = entity.get(StatusEffectsComponent).status_effects
        assert len(effects) == 1
        assert effects[0].name == "中毒"
        assert effects[0].description == "新"

    def test_field_validation(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        """speed 超范围归一化；defense 正负值保留原值，缺省为 0。"""
        entity = _make_actor_entity(context, "刺客", with_action=True)
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
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        entity = _make_actor_entity(context, "骑士", with_action=True)
        mock_game.get_entity_by_name.return_value = entity
        system._process_status_effects_response(
            _make_mock_chat_client("骑士", "不是JSON")
        )
        assert entity.get(StatusEffectsComponent).status_effects == []

    def test_condensed_prompt_mode(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        """use_condensed_prompt=True 时 message_content 应为 condensed_prompt。"""
        entity = _make_actor_entity(context, "猎人", with_action=True)
        mock_game.get_entity_by_name.return_value = entity
        client = _make_mock_chat_client(
            "猎人", '{"add_effects": []}', prompt="full", condensed_prompt="condensed"
        )
        system._process_status_effects_response(client)
        assert (
            mock_game.add_human_message.call_args[1]["human_message"].content
            == "condensed"
        )

    def test_full_prompt_mode(
        self,
        context: Context,
        mock_game: MagicMock,
        system_no_condense: UpdateStatusEffectsActionSystem,
    ) -> None:
        """use_condensed_prompt=False 时 message_content 应为 full prompt。"""
        entity = _make_actor_entity(context, "游侠", with_action=True)
        mock_game.get_entity_by_name.return_value = entity
        client = _make_mock_chat_client(
            "游侠",
            '{"add_effects": []}',
            prompt="full prompt content",
            condensed_prompt="condensed",
        )
        system_no_condense._process_status_effects_response(client)
        assert (
            mock_game.add_human_message.call_args[1]["human_message"].content
            == "full prompt content"
        )


# ---------------------------------------------------------------------------
# Phase 3 — 异步 react()
# ---------------------------------------------------------------------------


class TestUpdateStatusEffectsActionSystemReact:
    @pytest.mark.asyncio
    async def test_skips_when_not_ongoing(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        """战斗未进行中时，batch_chat 不应被调用。"""
        mock_game.current_dungeon_combat_room.combat.is_ongoing = False
        entity = _make_actor_entity(context, "英雄", with_action=True)
        with patch(
            "src.ai_rpg.systems.update_status_effects_action_system.batch_chat",
            new_callable=AsyncMock,
        ) as mock_batch:
            await system.react([entity])
            mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_chat_called_with_correct_count(
        self,
        context: Context,
        mock_game: MagicMock,
        system: UpdateStatusEffectsActionSystem,
    ) -> None:
        """2 个 actor → batch_chat 收到 2 个 client。"""
        mock_game.current_dungeon_combat_room.combat.is_ongoing = True
        mock_game.current_dungeon_combat_room.combat.rounds = [1, 2]
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
                "src.ai_rpg.systems.update_status_effects_action_system.batch_chat",
                side_effect=_capture,
            ),
            patch.object(system, "_process_status_effects_response"),
        ):
            await system.react([actor1, actor2])

        assert len(captured) == 2

    def test_filter_rejects_dead_actor(
        self, context: Context, system: UpdateStatusEffectsActionSystem
    ) -> None:
        entity = _make_actor_entity(context, "亡灵", with_action=True, dead=True)
        assert system.filter(entity) is False

    def test_filter_accepts_valid_actor(
        self, context: Context, system: UpdateStatusEffectsActionSystem
    ) -> None:
        entity = _make_actor_entity(context, "勇士", with_action=True)
        assert system.filter(entity) is True


# ---------------------------------------------------------------------------
