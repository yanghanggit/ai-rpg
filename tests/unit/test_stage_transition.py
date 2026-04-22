"""
Unit tests for src/ai_rpg/game/stage_transition.py

覆盖范围：
  - 3 个格式化纯函数
  - _validate_stage_transition_prerequisites（用 Mock game）
  - stage_transition 完整流程（用真实 TCGGame fixture）
"""

import pytest
from typing import Any
from unittest.mock import MagicMock

from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.models import (
    ActorComponent,
    PlayerComponent,
    PlayerOnlyStageComponent,
    StageComponent,
)
from src.ai_rpg.game.stage_transition import (
    _format_stage_arrival_message,
    _format_stage_departure_message,
    _format_stage_transition_message,
    _validate_stage_transition_prerequisites,
    stage_transition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stage(game: Any, stage_name: str) -> Entity:
    """在 game 中创建一个带 StageComponent 的场景实体。"""
    entity: Entity = game._create_entity(stage_name)
    entity.add(StageComponent, stage_name, "")
    return entity


def _make_actor(game: Any, actor_name: str, current_stage_name: str) -> Entity:
    """在 game 中创建一个带 ActorComponent 的角色实体。"""
    entity: Entity = game._create_entity(actor_name)
    entity.add(ActorComponent, actor_name, "sheet", current_stage_name)
    return entity


def _make_player_actor(game: Any, actor_name: str, current_stage_name: str) -> Entity:
    """在 game 中创建一个带 ActorComponent + PlayerComponent 的玩家实体。"""
    entity = _make_actor(game, actor_name, current_stage_name)
    entity.add(PlayerComponent, "player_session")
    return entity


# ---------------------------------------------------------------------------
# 格式化纯函数
# ---------------------------------------------------------------------------


class TestFormatFunctions:
    def test_departure_message(self) -> None:
        msg = _format_stage_departure_message("英雄", "起点")
        assert msg == "# 英雄 离开了场景: 起点"

    def test_arrival_message(self) -> None:
        msg = _format_stage_arrival_message("英雄", "终点")
        assert msg == "# 英雄 进入了 场景: 终点"

    def test_transition_message(self) -> None:
        msg = _format_stage_transition_message("起点", "终点")
        assert msg == "# 你从 场景: 起点 离开，然后进入了 场景: 终点"

    def test_departure_message_special_chars(self) -> None:
        msg = _format_stage_departure_message("勇者·甲", "地下城-1F")
        assert "勇者·甲" in msg
        assert "地下城-1F" in msg

    def test_transition_message_includes_both_stages(self) -> None:
        msg = _format_stage_transition_message("A", "B")
        assert "A" in msg
        assert "B" in msg


# ---------------------------------------------------------------------------
# _validate_stage_transition_prerequisites（Mock game）
# ---------------------------------------------------------------------------


class TestValidateStageTransitionPrerequisites:
    """使用 MagicMock game 独立测试前置条件校验逻辑。"""

    def _mock_game(self, actor_to_stage: dict[Any, Any]) -> Any:
        """构造一个 mock game，resolve_stage_entity 按传入映射返回场景。"""
        game = MagicMock()
        game.resolve_stage_entity.side_effect = lambda e: actor_to_stage.get(e)
        return game

    def _mock_actor(self, has_actor_component: bool = True) -> Any:
        """构造一个带/不带 ActorComponent 的 mock actor。"""
        actor = MagicMock()
        actor.name = "mock_actor"

        def _has(comp: Any) -> bool:
            return has_actor_component if comp is ActorComponent else False

        actor.has.side_effect = _has
        return actor

    def test_actor_without_actor_component_raises(self) -> None:
        """缺少 ActorComponent 的角色应触发 AssertionError。"""
        actor = self._mock_actor(has_actor_component=False)
        dest = MagicMock()
        game = self._mock_game({})

        with pytest.raises(AssertionError, match="缺少 ActorComponent"):
            _validate_stage_transition_prerequisites(game, {actor}, dest)

    def test_actor_already_at_destination_is_filtered_out(self) -> None:
        """已在目标场景的角色应被过滤，返回空集合。"""
        dest = MagicMock()
        actor = self._mock_actor()
        game = self._mock_game({actor: dest})

        result = _validate_stage_transition_prerequisites(game, {actor}, dest)

        assert result == set()

    def test_actor_at_different_stage_is_included(self) -> None:
        """处于其他场景的角色应包含在返回集合中。"""
        dest = MagicMock()
        source = MagicMock()
        actor = self._mock_actor()
        game = self._mock_game({actor: source})

        result = _validate_stage_transition_prerequisites(game, {actor}, dest)

        assert result == {actor}

    def test_mixed_actors_partial_filter(self) -> None:
        """部分在目标场景、部分不在：只返回需要传送的角色。"""
        dest = MagicMock()
        source = MagicMock()
        actor_at_dest = self._mock_actor()
        actor_at_source = self._mock_actor()
        actor_at_source.name = "actor_at_source"

        game = self._mock_game({actor_at_dest: dest, actor_at_source: source})

        result = _validate_stage_transition_prerequisites(
            game, {actor_at_dest, actor_at_source}, dest
        )

        assert result == {actor_at_source}


# ---------------------------------------------------------------------------
# stage_transition 完整流程（真实 TCGGame）
# ---------------------------------------------------------------------------


class TestStageTransition:
    """使用真实 TCGGame（sample_game fixture）测试完整场景转换流程。"""

    @pytest.fixture
    def game(self, sample_game: Any) -> Any:
        return sample_game

    # ------------------------------------------------------------------
    # 基础传送
    # ------------------------------------------------------------------

    def test_actor_current_stage_updated_after_transfer(self, game: Any) -> None:
        """传送后 ActorComponent.current_stage 应指向目标场景。"""
        source = _make_stage(game, "起点")
        dest = _make_stage(game, "终点")
        actor = _make_actor(game, "英雄", source.name)

        stage_transition(game, {actor}, dest)

        actor_comp = actor.get(ActorComponent)
        assert actor_comp is not None
        assert actor_comp.current_stage == dest.name

    def test_resolve_stage_entity_returns_destination_after_transfer(
        self, game: Any
    ) -> None:
        """传送后 resolve_stage_entity 应解析到目标场景实体。"""
        source = _make_stage(game, "起点")
        dest = _make_stage(game, "终点")
        actor = _make_actor(game, "英雄", source.name)

        stage_transition(game, {actor}, dest)

        assert game.resolve_stage_entity(actor) is dest

    def test_empty_actors_set_does_nothing(self, game: Any) -> None:
        """空角色集合不应改变任何状态。"""
        dest = _make_stage(game, "终点")
        # 不抛异常，context 无变化
        stage_transition(game, set(), dest)

    def test_transfer_to_same_stage_is_noop(self, game: Any) -> None:
        """角色已在目标场景时传送为空操作，current_stage 不变。"""
        source = _make_stage(game, "场景A")
        actor = _make_actor(game, "英雄", source.name)

        stage_transition(game, {actor}, source)

        actor_comp = actor.get(ActorComponent)
        assert actor_comp is not None
        assert actor_comp.current_stage == source.name

    def test_multiple_actors_all_transferred(self, game: Any) -> None:
        """多个角色应全部被传送到目标场景。"""
        source = _make_stage(game, "起点")
        dest = _make_stage(game, "终点")
        actor_a = _make_actor(game, "英雄A", source.name)
        actor_b = _make_actor(game, "英雄B", source.name)

        stage_transition(game, {actor_a, actor_b}, dest)

        for actor in (actor_a, actor_b):
            comp = actor.get(ActorComponent)
            assert comp is not None
            assert comp.current_stage == dest.name

    # ------------------------------------------------------------------
    # 消息广播验证
    # ------------------------------------------------------------------

    def test_actor_context_receives_transition_self_message(self, game: Any) -> None:
        """角色自身 context 中应存在包含起点/终点的场景转换消息。"""
        source = _make_stage(game, "起点")
        dest = _make_stage(game, "终点")
        actor = _make_actor(game, "英雄", source.name)

        stage_transition(game, {actor}, dest)

        messages = game.get_agent_context(actor).context
        contents = [m.content for m in messages]
        assert any(
            "起点" in c and "终点" in c for c in contents
        ), f"未在 actor context 中找到含起点/终点的转换消息，实际消息: {contents}"

    def test_source_stage_context_receives_departure_message(self, game: Any) -> None:
        """起点场景 context 中应存在角色离开的广播消息。"""
        source = _make_stage(game, "起点")
        dest = _make_stage(game, "终点")
        actor = _make_actor(game, "英雄", source.name)

        stage_transition(game, {actor}, dest)

        messages = game.get_agent_context(source).context
        contents = [m.content for m in messages]
        assert any(
            "离开" in c for c in contents
        ), f"未在起点场景 context 中找到离开消息，实际消息: {contents}"

    def test_destination_stage_context_receives_arrival_message(
        self, game: Any
    ) -> None:
        """终点场景 context 中应存在角色到达的广播消息。"""
        source = _make_stage(game, "起点")
        dest = _make_stage(game, "终点")
        actor = _make_actor(game, "英雄", source.name)

        stage_transition(game, {actor}, dest)

        messages = game.get_agent_context(dest).context
        contents = [m.content for m in messages]
        assert any(
            "进入" in c for c in contents
        ), f"未在终点场景 context 中找到到达消息，实际消息: {contents}"

    # ------------------------------------------------------------------
    # PlayerOnlyStage 访问控制
    # ------------------------------------------------------------------

    def test_non_player_entering_player_only_stage_raises(self, game: Any) -> None:
        """非玩家角色尝试进入仅玩家场景应触发 AssertionError。"""
        source = _make_stage(game, "起点")
        dest = _make_stage(game, "玩家专属")
        dest.add(PlayerOnlyStageComponent, "玩家专属")
        actor = _make_actor(game, "NPC", source.name)

        with pytest.raises(AssertionError, match="不是玩家"):
            stage_transition(game, {actor}, dest)

    def test_player_actor_can_enter_player_only_stage(self, game: Any) -> None:
        """持有 PlayerComponent 的角色可以进入仅玩家场景，传送正常完成。"""
        source = _make_stage(game, "起点")
        dest = _make_stage(game, "玩家专属")
        dest.add(PlayerOnlyStageComponent, "玩家专属")
        player = _make_player_actor(game, "玩家", source.name)

        stage_transition(game, {player}, dest)

        comp = player.get(ActorComponent)
        assert comp is not None
        assert comp.current_stage == dest.name
