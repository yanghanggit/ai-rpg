"""
Unit tests for src/ai_rpg/game/rpg_game.py

覆盖范围（不重复 test_rpg_game_context.py 中已有的用例）：
  - get_agent_context
  - destroy_entity（含 agents_context 清理）
  - add_system_message
  - flush_entities / restore_from_snapshot
  - notify_entities
  - broadcast_to_stage
  - exit / initialize（冒烟测试）
"""

import uuid
import pytest
from typing import Any, cast

from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.models import (
    ActorComponent,
    IdentityComponent,
    StageComponent,
)
from src.ai_rpg.models.agent_event import AgentEvent
from src.ai_rpg.models.messages import SystemMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stage(game: Any, stage_name: str) -> Entity:
    """创建带 StageComponent 的场景实体。"""
    entity: Entity = game._create_entity(stage_name)
    entity.add(StageComponent, stage_name, "")
    return entity


def _make_actor(game: Any, actor_name: str, current_stage_name: str) -> Entity:
    """创建带 ActorComponent 的角色实体。"""
    entity: Entity = game._create_entity(actor_name)
    entity.add(ActorComponent, actor_name, "sheet", current_stage_name)
    return entity


def _make_entity_with_identity(game: Any, name: str, order: int) -> Entity:
    """创建带 IdentityComponent 的实体（flush_entities 排序所需）。"""
    entity: Entity = game._create_entity(name)
    entity.add(IdentityComponent, name, order, str(uuid.uuid4()))
    return entity


def _agent_event(message: str = "hello") -> AgentEvent:
    return AgentEvent(message=message)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def game(sample_game: Any) -> Any:
    return sample_game


@pytest.fixture
def actor(game: Any) -> Entity:
    return cast(Entity, game._create_entity("Actor_A"))


@pytest.fixture
def second_actor(game: Any) -> Entity:
    return cast(Entity, game._create_entity("Actor_B"))


# ---------------------------------------------------------------------------
# get_agent_context
# ---------------------------------------------------------------------------


class TestGetAgentContext:
    def test_creates_context_on_first_access(self, game: Any, actor: Entity) -> None:
        """首次访问不存在的实体时，自动创建 AgentContext。"""
        assert actor.name not in game._world.agents_context
        ctx = game.get_agent_context(actor)
        assert ctx is not None
        assert actor.name in game._world.agents_context

    def test_returns_same_object_on_repeated_call(
        self, game: Any, actor: Entity
    ) -> None:
        """同一实体重复调用返回同一对象（identity）。"""
        ctx1 = game.get_agent_context(actor)
        ctx2 = game.get_agent_context(actor)
        assert ctx1 is ctx2

    def test_context_name_matches_entity(self, game: Any, actor: Entity) -> None:
        """返回的 AgentContext.name 与实体名称一致。"""
        ctx = game.get_agent_context(actor)
        assert ctx.name == actor.name

    def test_different_entities_have_independent_contexts(
        self, game: Any, actor: Entity, second_actor: Entity
    ) -> None:
        """不同实体各自拥有独立的 AgentContext 对象。"""
        ctx_a = game.get_agent_context(actor)
        ctx_b = game.get_agent_context(second_actor)
        assert ctx_a is not ctx_b
        assert ctx_a.name != ctx_b.name


# ---------------------------------------------------------------------------
# destroy_entity
# ---------------------------------------------------------------------------


class TestDestroyEntity:
    def test_destroy_removes_from_name_index(self, game: Any, actor: Entity) -> None:
        """销毁后 get_entity_by_name 返回 None。"""
        game.destroy_entity(actor)
        assert game.get_entity_by_name(actor.name) is None

    def test_destroy_cleans_up_agents_context(self, game: Any, actor: Entity) -> None:
        """销毁时，world.agents_context 中对应 key 被移除。"""
        game.get_agent_context(actor)  # ensure context exists
        assert actor.name in game._world.agents_context
        game.destroy_entity(actor)
        assert actor.name not in game._world.agents_context

    def test_destroy_entity_without_context_ok(self, game: Any, actor: Entity) -> None:
        """没有 agents_context 的实体销毁时不抛异常。"""
        assert actor.name not in game._world.agents_context
        game.destroy_entity(actor)  # should not raise
        assert game.get_entity_by_name(actor.name) is None


# ---------------------------------------------------------------------------
# add_system_message
# ---------------------------------------------------------------------------


class TestAddSystemMessage:
    def test_basic_system_message(self, game: Any, actor: Entity) -> None:
        """成功添加 SystemMessage，内容与类型正确。"""
        game.add_system_message(actor, "system prompt")
        ctx = game.get_agent_context(actor).context
        assert len(ctx) == 1
        assert isinstance(ctx[0], SystemMessage)
        assert ctx[0].content == "system prompt"

    def test_system_message_not_first_raises(self, game: Any, actor: Entity) -> None:
        """context 非空时调用 add_system_message 触发 AssertionError。"""
        game.add_human_message(actor, "already something here")
        with pytest.raises(AssertionError):
            game.add_system_message(actor, "system prompt")


# ---------------------------------------------------------------------------
# flush_entities / restore_from_snapshot
# ---------------------------------------------------------------------------


class TestFlushAndRestoreSnapshot:
    def test_flush_populates_entities_serialization(self, game: Any) -> None:
        """flush_entities 后 world.entities_serialization 非空。"""
        _make_entity_with_identity(game, "EntityX", 1)
        game.flush_entities()
        assert len(game._world.entities_serialization) > 0

    def test_restore_from_empty_raises(self, game: Any) -> None:
        """entities_serialization 为空时 restore_from_snapshot 触发 AssertionError。"""
        assert len(game._world.entities_serialization) == 0
        with pytest.raises(AssertionError):
            game.restore_from_snapshot()

    def test_restore_with_existing_entities_raises(self, game: Any) -> None:
        """游戏中已有实体时 restore_from_snapshot 触发 AssertionError。"""
        entity = _make_entity_with_identity(game, "EntityY", 1)
        game.flush_entities()
        # Now entities exist AND serialization is non-empty → should raise
        with pytest.raises(AssertionError):
            game.restore_from_snapshot()

    def test_flush_then_restore_round_trip(self, game: Any) -> None:
        """flush → 销毁所有实体 → restore：实体可通过名称找回。"""
        e1 = _make_entity_with_identity(game, "EntityR1", 1)
        e2 = _make_entity_with_identity(game, "EntityR2", 2)

        # Flush: persist current state
        game.flush_entities()
        assert len(game._world.entities_serialization) == 2

        # Destroy all entities
        game.destroy_entity(e1)
        game.destroy_entity(e2)
        assert len(game._entities) == 0

        # Restore: recreate entities from snapshot
        game.restore_from_snapshot()
        assert game.get_entity_by_name("EntityR1") is not None
        assert game.get_entity_by_name("EntityR2") is not None


# ---------------------------------------------------------------------------
# notify_entities
# ---------------------------------------------------------------------------


class TestNotifyEntities:
    def test_notify_adds_message_to_all_entities(
        self, game: Any, actor: Entity, second_actor: Entity
    ) -> None:
        """notify_entities 把事件消息添加给集合中的每个实体。"""
        event = _agent_event("broadcast")
        game.notify_entities({actor, second_actor}, event)

        assert game.get_agent_context(actor).context[-1].content == "broadcast"
        assert game.get_agent_context(second_actor).context[-1].content == "broadcast"

    def test_notify_sends_to_player_session(self, game: Any, actor: Entity) -> None:
        """notify_entities 向 player_session 发送 SessionMessage。"""
        before = len(game._player_session.session_messages)
        game.notify_entities({actor}, _agent_event("event1"))
        assert len(game._player_session.session_messages) == before + 1

    def test_notify_empty_set_still_sends_to_player(self, game: Any) -> None:
        """实体集合为空时，玩家仍收到事件（session_messages 增加）。"""
        before = len(game._player_session.session_messages)
        game.notify_entities(set(), _agent_event("empty broadcast"))
        assert len(game._player_session.session_messages) == before + 1

    def test_player_session_event_sequence_increments(
        self, game: Any, actor: Entity
    ) -> None:
        """每次 notify_entities 后 player_session.event_sequence 递增。"""
        seq_before = game._player_session.event_sequence
        game.notify_entities({actor}, _agent_event("seq test"))
        assert game._player_session.event_sequence == seq_before + 1


# ---------------------------------------------------------------------------
# broadcast_to_stage
# ---------------------------------------------------------------------------


class TestBroadcastToStage:
    def test_broadcast_reaches_stage_and_actors(self, game: Any) -> None:
        """广播时，场景实体及其所有 actor 都收到消息。"""
        stage = _make_stage(game, "Stage_1")
        a1 = _make_actor(game, "NPC_1", "Stage_1")
        a2 = _make_actor(game, "NPC_2", "Stage_1")

        game.broadcast_to_stage(stage, _agent_event("stage msg"))

        assert game.get_agent_context(stage).context[-1].content == "stage msg"
        assert game.get_agent_context(a1).context[-1].content == "stage msg"
        assert game.get_agent_context(a2).context[-1].content == "stage msg"

    def test_broadcast_excludes_specified_entities(self, game: Any) -> None:
        """被排除的实体不收到广播消息。"""
        stage = _make_stage(game, "Stage_2")
        a1 = _make_actor(game, "NPC_3", "Stage_2")
        a2 = _make_actor(game, "NPC_4", "Stage_2")

        game.broadcast_to_stage(stage, _agent_event("exclusive"), exclude_entities={a2})

        # a1 and stage get it, a2 is excluded
        assert game.get_agent_context(a1).context[-1].content == "exclusive"
        assert game.get_agent_context(stage).context[-1].content == "exclusive"
        assert len(game.get_agent_context(a2).context) == 0

    def test_broadcast_with_no_actors_reaches_stage_only(self, game: Any) -> None:
        """场景中无 actor 时，只有场景实体收到广播。"""
        stage = _make_stage(game, "Stage_3")
        other_stage = _make_stage(game, "Stage_other")  # must exist for actor resolve
        unrelated_actor = _make_actor(game, "NPC_5", "Stage_other")

        game.broadcast_to_stage(stage, _agent_event("empty stage msg"))

        assert game.get_agent_context(stage).context[-1].content == "empty stage msg"
        assert len(game.get_agent_context(unrelated_actor).context) == 0

    def test_broadcast_asserts_on_entity_without_stage(self, game: Any) -> None:
        """传入没有 StageComponent 也没有 ActorComponent 的实体触发 AssertionError。"""
        plain_entity = game._create_entity("PlainEntity")
        with pytest.raises(AssertionError):
            game.broadcast_to_stage(plain_entity, _agent_event("fail"))


# ---------------------------------------------------------------------------
# exit / initialize（冒烟测试）
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_exit_with_no_pipelines(self, game: Any) -> None:
        """无管道时 exit() 不抛异常。"""
        game.exit()  # should not raise

    async def test_initialize_with_no_pipelines(self, game: Any) -> None:
        """无管道时 initialize() 不抛异常。"""
        await game.initialize()
