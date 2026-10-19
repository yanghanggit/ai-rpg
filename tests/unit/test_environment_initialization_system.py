"""EnvironmentInitializationSystem 的「无观察 = 无推理」观察者门槛测试。

观察者门槛：
- Home 场景：场景内存在存活 Actor（有人）即请求环境叙事；
- Dungeon 场景：场景内存在存活 Actor，且玩家本人在场，才请求；
其余场景保持惰性，跳过推理。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_rpg.deepseek import DeepSeekError
from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.llm import ChatCompletionRequest, ChatCompletionResult
from ai_rpg.models import (
    AIMessage,
    DungeonComponent,
    EnvironmentComponent,
    HomeComponent,
    PlayerComponent,
    StageComponent,
)
from ai_rpg.systems.environment_initialization_system import (
    EnvironmentInitializationSystem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stage(context: Context, name: str, *, dungeon: bool = False) -> Entity:
    stage = context.create_entity()
    stage._name = name
    stage.add(StageComponent, name)
    stage.add(DungeonComponent if dungeon else HomeComponent, name)
    return stage


def _fake_actor(*, is_player: bool = False) -> MagicMock:
    """构造仅需支持 .has(PlayerComponent) 语义的假 Actor。"""
    actor = MagicMock()
    actor.has.side_effect = lambda comp: is_player and comp is PlayerComponent
    return actor


def _fake_request(name: str) -> MagicMock:
    request = MagicMock(spec=ChatCompletionRequest)
    request.label = name
    return request


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
def system(mock_game: MagicMock) -> EnvironmentInitializationSystem:
    return EnvironmentInitializationSystem(mock_game)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestObservedStagesOnly:
    @pytest.mark.asyncio
    async def test_home_stage_with_actors_is_inferred(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EnvironmentInitializationSystem,
    ) -> None:
        """Home 场景：有 Actor 即构建请求；无 Actor 的 Home 场景被跳过。"""
        observed = _make_stage(context, "场景.酒馆")
        empty = _make_stage(context, "场景.佣兵公会")
        mock_game.get_group.return_value.entities.copy.return_value = {observed, empty}

        def _has_actors(_game: DBGGame, stage: Entity) -> set[MagicMock]:
            return {_fake_actor()} if stage is observed else set()

        with (
            patch(
                "ai_rpg.systems.environment_initialization_system.get_alive_actors_in_stage",
                side_effect=_has_actors,
            ),
            patch.object(
                system,
                "_build_request",
                side_effect=lambda stage: _fake_request(stage.name),
            ),
            patch.object(system, "_process_environment_response"),
            patch(
                "ai_rpg.systems.environment_initialization_system.batch_complete",
                new=AsyncMock(),
            ) as mock_batch,
        ):
            await system.execute()

        sent_names = [r.label for r in mock_batch.call_args.args[0]]
        assert sent_names == ["场景.酒馆"]

    @pytest.mark.asyncio
    async def test_dungeon_stage_without_player_is_skipped(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EnvironmentInitializationSystem,
    ) -> None:
        """Dungeon 场景：即便有 Actor，只要玩家不在场就不构建请求。"""
        dungeon = _make_stage(context, "副本.荒狼巢", dungeon=True)
        mock_game.get_group.return_value.entities.copy.return_value = {dungeon}

        with (
            patch(
                "ai_rpg.systems.environment_initialization_system.get_alive_actors_in_stage",
                side_effect=lambda _game, _stage: {_fake_actor(), _fake_actor()},
            ),
            patch(
                "ai_rpg.systems.environment_initialization_system.batch_complete",
                new=AsyncMock(),
            ) as mock_batch,
        ):
            await system.execute()

        mock_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_dungeon_stage_with_player_is_inferred(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EnvironmentInitializationSystem,
    ) -> None:
        """Dungeon 场景：有 Actor 且玩家在场时才构建请求。"""
        dungeon = _make_stage(context, "副本.荒狼巢", dungeon=True)
        mock_game.get_group.return_value.entities.copy.return_value = {dungeon}

        with (
            patch(
                "ai_rpg.systems.environment_initialization_system.get_alive_actors_in_stage",
                side_effect=lambda _game, _stage: {
                    _fake_actor(),
                    _fake_actor(is_player=True),
                },
            ),
            patch.object(
                system,
                "_build_request",
                side_effect=lambda stage: _fake_request(stage.name),
            ),
            patch.object(system, "_process_environment_response"),
            patch(
                "ai_rpg.systems.environment_initialization_system.batch_complete",
                new=AsyncMock(),
            ) as mock_batch,
        ):
            await system.execute()

        sent_names = [r.label for r in mock_batch.call_args.args[0]]
        assert sent_names == ["副本.荒狼巢"]

    @pytest.mark.asyncio
    async def test_no_observed_stages_skips_inference(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EnvironmentInitializationSystem,
    ) -> None:
        """所有缺环境场景都没有 Actor 时，直接返回，不发起任何请求。"""
        a = _make_stage(context, "场景.酒馆")
        b = _make_stage(context, "场景.佣兵公会")
        mock_game.get_group.return_value.entities.copy.return_value = {a, b}

        with (
            patch(
                "ai_rpg.systems.environment_initialization_system.get_alive_actors_in_stage",
                return_value=set(),
            ),
            patch(
                "ai_rpg.systems.environment_initialization_system.batch_complete",
                new=AsyncMock(),
            ) as mock_batch,
        ):
            await system.execute()

        mock_batch.assert_not_called()


class TestFailureAccounting:
    @pytest.mark.asyncio
    async def test_writes_successes_and_skips_failed(
        self,
        context: Context,
        mock_game: MagicMock,
        system: EnvironmentInitializationSystem,
    ) -> None:
        """消费 batch 失败列表：成功场景写入组件，失败场景不写入且不再走 response 解析。"""
        ok = _make_stage(context, "场景.兽径入口")
        bad = _make_stage(context, "场景.佣兵公会")
        # 用 list（而非 set）固定顺序，使 batch 返回的结果与 requests 对齐可预测
        mock_game.get_group.return_value.entities = [ok, bad]
        mock_game.get_entity_by_name.side_effect = lambda n: {
            "场景.兽径入口": ok,
            "场景.佣兵公会": bad,
        }[n]

        def _build(stage: Entity) -> ChatCompletionRequest:
            return ChatCompletionRequest(
                label=stage.name,
                input_message=f"prompt:{stage.name}",
                messages=[],
            )

        ok_result = ChatCompletionResult(
            request=_build(ok), ai_message=AIMessage(content="松林窄径，泥泞湿冷")
        )
        bad_result = ChatCompletionResult(
            request=_build(bad),
            error=DeepSeekError("场景.佣兵公会", "timeout", kind="timeout"),
        )

        with (
            patch(
                "ai_rpg.systems.environment_initialization_system.get_alive_actors_in_stage",
                return_value={_fake_actor()},
            ),
            patch.object(system, "_build_request", side_effect=_build),
            patch(
                "ai_rpg.systems.environment_initialization_system.batch_complete",
                new=AsyncMock(return_value=[ok_result, bad_result]),
            ),
        ):
            await system.execute()

        # 成功场景写入环境叙事
        assert ok.has(EnvironmentComponent)
        assert ok.get(EnvironmentComponent).narrative == "松林窄径，泥泞湿冷"
        # 失败场景未写入，且未进入 response 解析（get_entity_by_name 仅对成功项调用）
        assert not bad.has(EnvironmentComponent)
        mock_game.get_entity_by_name.assert_called_once_with("场景.兽径入口")
