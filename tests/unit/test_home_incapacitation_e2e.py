"""家园 NPC 失能功能端到端测试。

用真实 DBGGame（真 ECS group / 真记忆）跑一遍完整链路，只 mock LLM 摘要调用：
  1. lives 归零的家园 NPC → HomeNpcIncapacitationSystem 压缩记忆并挂 IncapacitatedComponent
  2. 挂载后「彻底失能」的所有下游闸口同时生效：
     - 不能规划行动（HomeNpcPlanSystem.filter 拒绝）
     - 不能收集信息（add_human_message 断言失败）
     - 不能加入队伍名单（add_party_member 拒绝）
     - 不能激活行动计划（activate_plan_action 拒绝）
     - 已从玩家队伍名单移除
"""

from typing import Any
from unittest.mock import patch

import pytest

from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    CharacterStats,
    CharacterStatsComponent,
    HomeComponent,
    IncapacitatedComponent,
    NPCComponent,
    PartyRosterComponent,
    PlanAction,
    PlayerComponent,
    StageComponent,
)
from ai_rpg.models.messages import AIMessage, HumanMessage, SystemMessage
from ai_rpg.services.home_actions import (
    activate_plan_action,
    add_party_member,
)
from ai_rpg.systems.home_npc_incapacitation_system import (
    HomeNpcIncapacitationSystem,
)
from ai_rpg.systems.home_npc_plan_system import HomeNpcPlanSystem

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_home_stage(game: DBGGame, name: str) -> Entity:
    stage = game._create_entity(name)
    stage.add(StageComponent, name)
    stage.add(HomeComponent, name)
    return stage


def _make_player(game: DBGGame, name: str, stage_name: str) -> Entity:
    player = game._create_entity(name)
    player.add(ActorComponent, name, stage_name)
    player.add(PlayerComponent, name)
    player.add(NPCComponent, name)
    return player


def _make_npc(game: DBGGame, name: str, stage_name: str, *, lives: int) -> Entity:
    npc = game._create_entity(name)
    npc.add(ActorComponent, name, stage_name)
    npc.add(NPCComponent, name)
    npc.add(CharacterStatsComponent, name, CharacterStats(lives=lives))
    return npc


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incapacitation_end_to_end(sample_game: DBGGame) -> None:
    game: DBGGame = sample_game

    _make_home_stage(game, "场景.家园")
    player = _make_player(game, "角色.玩家", "场景.家园")
    player.add(PartyRosterComponent, "角色.玩家", ["角色.NPC_A"])

    npc = _make_npc(game, "角色.NPC_A", "场景.家园", lives=0)
    game.add_system_message(npc, SystemMessage(content="sys"))
    game.add_human_message(npc, HumanMessage(content="memory-1"))
    game.add_human_message(npc, HumanMessage(content="memory-2"))

    # 前提：未失能时是正常可规划、可入队的家园 NPC
    npc.add(PlanAction, npc.name)
    assert HomeNpcPlanSystem(game).filter(npc) is True
    npc.remove(PlanAction)

    async def fake_batch_chat(clients: Any) -> None:
        for client in clients:
            client._response_ai_message = AIMessage(content="summary")

    with patch(
        "ai_rpg.systems.home_npc_incapacitation_system.batch_chat",
        side_effect=fake_batch_chat,
    ):
        await HomeNpcIncapacitationSystem(game).execute()

    # 1. 已标记失能，且记忆被压缩为「system + 摘要」
    assert npc.has(IncapacitatedComponent)
    contents = [m.content for m in game.get_agent_memory(npc).messages]
    assert contents == ["sys", "summary"]

    # 2. 已从玩家队伍名单移除（名单只有该成员 → 组件整体移除）
    assert not player.has(PartyRosterComponent)

    # 3. 不能加入队伍名单
    ok, err = add_party_member(game, "角色.NPC_A")
    assert ok is False
    assert "失能" in err

    # 4. 不能激活行动计划，且不会挂上 PlanAction
    ok, err = activate_plan_action(game, ["角色.NPC_A"])
    assert ok is False
    assert "失能" in err
    assert not npc.has(PlanAction)

    # 5. 不能收集信息
    with pytest.raises(AssertionError):
        game.add_human_message(npc, HumanMessage(content="should fail"))

    # 6. 即使被强行挂上 PlanAction，规划系统也会拒绝
    npc.add(PlanAction, npc.name)
    assert HomeNpcPlanSystem(game).filter(npc) is False
