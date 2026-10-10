"""HomeNpcIncapacitationSystem 单元测试。

覆盖四个关键行为：
1. lives 耗尽的家园 NPC：压缩记忆 + 挂载 IncapacitatedComponent + 移出队伍名单
2. lives 未耗尽：不处理
3. 无可压缩内容：仍标记失能，但不发起 LLM 压缩
4. 非家园场景的 NPC：不处理
"""

from types import SimpleNamespace
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    CharacterStats,
    CharacterStatsComponent,
    IncapacitatedComponent,
    NPCComponent,
    PartyRosterComponent,
)
from ai_rpg.models.messages import AIMessage, HumanMessage, SystemMessage
from ai_rpg.systems.home_npc_incapacitation_system import (
    HomeNpcIncapacitationSystem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_npc(context: Context, name: str, *, lives: int) -> Entity:
    entity = context.create_entity()
    entity._name = name
    entity.add(ActorComponent, name, "场景.家园")
    entity.add(NPCComponent, name)
    entity.add(CharacterStatsComponent, name, CharacterStats(lives=lives))
    return entity


def _make_memory(name: str, message_count: int) -> SimpleNamespace:
    """构造带 1 条 system + (message_count-1) 条 human 的记忆。"""
    messages: List[Any] = [SystemMessage(content="sys")]
    messages.extend(HumanMessage(content=f"msg{i}") for i in range(message_count - 1))
    return SimpleNamespace(name=name, messages=messages)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def context() -> Context:
    return Context()


@pytest.fixture()
def mock_game() -> MagicMock:
    game = MagicMock(spec=DBGGame)
    # 默认无玩家 / 无队伍名单，避免 _remove_from_party_roster 走到未配置分支
    game.get_player_entity.return_value = None
    return game


@pytest.fixture()
def system(mock_game: MagicMock) -> HomeNpcIncapacitationSystem:
    return HomeNpcIncapacitationSystem(mock_game)


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


class TestExecute:
    @pytest.mark.asyncio
    async def test_exhausted_npc_is_compacted_incapacitated_and_removed_from_roster(
        self,
        context: Context,
        mock_game: MagicMock,
        system: HomeNpcIncapacitationSystem,
    ) -> None:
        """lives==0 的家园 NPC：压缩记忆、挂载失能组件，并从玩家队伍名单移除。"""
        npc = _make_npc(context, "角色.NPC_A", lives=0)

        player = context.create_entity()
        player._name = "角色.玩家"
        player.add(PartyRosterComponent, "角色.玩家", ["角色.NPC_A"])

        mock_game.get_group.return_value = MagicMock(entities=[npc])
        mock_game.is_actor_in_home_stage.return_value = True
        mock_game.get_agent_memory.side_effect = lambda e: _make_memory(e.name, 3)
        mock_game.get_entity_by_name.side_effect = {"角色.NPC_A": npc}.get
        mock_game.get_player_entity.return_value = player

        async def fake_batch_chat(clients: List[Any]) -> None:
            for client in clients:
                client._response_ai_message = AIMessage(content="压缩后的摘要")

        with patch(
            "ai_rpg.systems.home_npc_incapacitation_system.batch_chat",
            side_effect=fake_batch_chat,
        ) as mock_batch:
            await system.execute()

        # 送入 batch_chat 的正是该 NPC
        sent_names = {client.name for client in mock_batch.call_args.kwargs["clients"]}
        assert sent_names == {"角色.NPC_A"}

        # 记忆被压缩
        mock_game.compact_agent_memory.assert_called_once()

        # 挂载失能组件
        assert npc.has(IncapacitatedComponent)

        # 唯一成员被移出后，队伍名单组件整体移除
        assert not player.has(PartyRosterComponent)

    @pytest.mark.asyncio
    async def test_healthy_npc_untouched(
        self,
        context: Context,
        mock_game: MagicMock,
        system: HomeNpcIncapacitationSystem,
    ) -> None:
        """lives>0 的家园 NPC 不应被处理。"""
        npc = _make_npc(context, "角色.NPC_A", lives=2)

        mock_game.get_group.return_value = MagicMock(entities=[npc])
        mock_game.is_actor_in_home_stage.return_value = True

        with patch(
            "ai_rpg.systems.home_npc_incapacitation_system.batch_chat"
        ) as mock_batch:
            await system.execute()

        mock_batch.assert_not_called()
        mock_game.compact_agent_memory.assert_not_called()
        assert not npc.has(IncapacitatedComponent)

    @pytest.mark.asyncio
    async def test_exhausted_without_compactible_memory_still_incapacitated(
        self,
        context: Context,
        mock_game: MagicMock,
        system: HomeNpcIncapacitationSystem,
    ) -> None:
        """lives==0 但仅有 system 消息：不发起压缩，但仍标记失能。"""
        npc = _make_npc(context, "角色.NPC_A", lives=0)

        mock_game.get_group.return_value = MagicMock(entities=[npc])
        mock_game.is_actor_in_home_stage.return_value = True
        mock_game.get_agent_memory.side_effect = lambda e: _make_memory(e.name, 1)

        with patch(
            "ai_rpg.systems.home_npc_incapacitation_system.batch_chat"
        ) as mock_batch:
            await system.execute()

        mock_batch.assert_not_called()
        mock_game.compact_agent_memory.assert_not_called()
        assert npc.has(IncapacitatedComponent)

    @pytest.mark.asyncio
    async def test_non_home_npc_skipped(
        self,
        context: Context,
        mock_game: MagicMock,
        system: HomeNpcIncapacitationSystem,
    ) -> None:
        """lives==0 但不在家园场景的 NPC 不应被处理。"""
        npc = _make_npc(context, "角色.NPC_A", lives=0)

        mock_game.get_group.return_value = MagicMock(entities=[npc])
        mock_game.is_actor_in_home_stage.return_value = False

        with patch(
            "ai_rpg.systems.home_npc_incapacitation_system.batch_chat"
        ) as mock_batch:
            await system.execute()

        mock_batch.assert_not_called()
        assert not npc.has(IncapacitatedComponent)

    @pytest.mark.asyncio
    async def test_roster_keeps_other_members(
        self,
        context: Context,
        mock_game: MagicMock,
        system: HomeNpcIncapacitationSystem,
    ) -> None:
        """队伍名单还有其他成员时，只移除失能者，保留其余成员。"""
        npc = _make_npc(context, "角色.NPC_A", lives=0)

        player = context.create_entity()
        player._name = "角色.玩家"
        player.add(PartyRosterComponent, "角色.玩家", ["角色.NPC_A", "角色.NPC_B"])

        mock_game.get_group.return_value = MagicMock(entities=[npc])
        mock_game.is_actor_in_home_stage.return_value = True
        mock_game.get_agent_memory.side_effect = lambda e: _make_memory(e.name, 1)
        mock_game.get_player_entity.return_value = player

        await system.execute()

        assert player.has(PartyRosterComponent)
        assert list(player.get(PartyRosterComponent).members) == ["角色.NPC_B"]
        assert npc.has(IncapacitatedComponent)
