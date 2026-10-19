"""真实 `DBGGame` 上的记忆写入链路测试（不 mock `add_human_message`）。

补的两个洞：
1. `TransferCardsActionSystem` 写 `received_card` 走的是真实写入 + 真实标记校验
   （单测里 mock 掉 `add_human_message` 时，标记漏登记这类问题抓不到）；
2. `agent_loop` 等直写路径绕过 `add_*` 校验，由**存档前的兜底闸门**拦住未登记标记。
"""

from pathlib import Path
from typing import Any, cast

import pytest

from ai_rpg.entitas.entity import Entity
from ai_rpg.game import world_persistence
from ai_rpg.models import (
    ActorComponent,
    AgentMemory,
    AppearanceComponent,
    Card,
    HandComponent,
    HumanMessage,
    MonsterComponent,
    PartyMemberComponent,
    PlayCardsAction,
    Round,
    TargetType,
)
from ai_rpg.systems.transfer_cards_action_system import TransferCardsActionSystem


#######################################################################################################
def _make_card(name: str = "递过去的肩", count: int = 2) -> Card:
    return Card(
        name=name,
        description="副本会落进对方手里。",
        cost=1,
        damage=0,
        hit_count=count,
        block=2,
        target_type=TargetType.SPREAD,
        transferable=True,
        source="角色.无名",
    )


def _make_actor(game: Any, name: str, *, monster: bool = False) -> Entity:
    entity = cast(Entity, game._create_entity(name))
    entity.add(ActorComponent, name, "场景.河湾芦苇丛")
    entity.add(AppearanceComponent, name, "基础体型", "外观描述")
    entity.add(HandComponent, name, [])
    if monster:
        entity.add(MonsterComponent, name)
    else:
        entity.add(PartyMemberComponent, name)
    return entity


def _arm_combat(game: Any) -> None:
    """造一个进行中的战斗房间（转移系统以此作为前置）。"""
    from ai_rpg.models import (
        Combat,
        CombatRoom,
        CombatState,
        Dungeon,
        Stage,
        StageType,
    )

    stage_model = Stage(
        name="场景.河湾芦苇丛",
        type=StageType.DUNGEON,
        profile="",
        system_message="stage",
        actors=[],
    )
    combat = Combat(name=stage_model.name)
    combat.state = CombatState.ONGOING
    combat.rounds = [Round(action_order=[], completed_actors=[])]
    game._world.dungeon = Dungeon(
        name="副本.断桥渡口",
        rooms=[CombatRoom(stage=stage_model, combat=combat)],
        profile="",
        current_room_index=0,
    )


#######################################################################################################
class TestTransferWritesRealMemory:
    async def test_received_card_memory_and_tags(
        self, sample_game: Any, tmp_path: Path
    ) -> None:
        """真实写入：接收方得到 `received_card` 标记的消息，标记能过校验并落盘。"""
        game = sample_game
        _arm_combat(game)
        giver = _make_actor(game, "角色.无名")
        receiver = _make_actor(game, "怪物.渡口野狗", monster=True)

        card = _make_card(count=2)  # 两击全落在同一目标 → 两份副本
        giver.get(HandComponent).cards.append(card)
        giver.add(PlayCardsAction, giver.name, card, [receiver.name, receiver.name])

        await TransferCardsActionSystem(game).react([giver])

        # 手牌：本体离开 + 接收方拿到两份副本
        assert giver.get(HandComponent).cards == []
        copies = receiver.get(HandComponent).cards
        assert len(copies) == 2
        assert all(c.name == card.name and not c.transferable for c in copies)

        # 记忆：接收方一条（带 received_card 标记），给出方一条（带 received_card 汇总）
        receiver_msgs = [
            m
            for m in game.get_agent_memory(receiver).messages
            if getattr(m, "received_card", None) is not None
        ]
        assert len(receiver_msgs) == 1
        assert '"name": "递过去的肩"' in receiver_msgs[0].received_card

        # 标记能过存档闸门（真实校验路径）
        save_dir = tmp_path / "snap"
        assert world_persistence.save_world(
            game._world, game._player_session, tmp_path, save_dir
        )
        restored, _ = world_persistence.restore_world(save_dir)
        assert any(
            getattr(m, "received_card", None) is not None
            for m in restored.agent_memories[receiver.name].messages
        )


#######################################################################################################
class TestSaveGateCatchesDirectWrites:
    """agent_loop 等直写路径不经过 add_* 校验，靠存档前的闸门兜底。"""

    def test_direct_append_with_unknown_tag_aborts_save(
        self, sample_game: Any, tmp_path: Path
    ) -> None:
        game = sample_game
        entity = _make_actor(game, "角色.无名")
        # 模拟直写：绕过 add_human_message，塞一个未登记标记
        game.get_agent_memory(entity).messages.append(
            HumanMessage(content="直写消息", loop_meta="v1")
        )

        with pytest.raises(AssertionError, match="未登记的记忆标记"):
            world_persistence.save_world(
                game._world, game._player_session, tmp_path, tmp_path / "snap"
            )

    def test_direct_append_with_loop_tags_saves(
        self, sample_game: Any, tmp_path: Path
    ) -> None:
        """agent_loop 真实用到的 loop_id / loop_id_end 等标记可以落盘。"""
        game = sample_game
        entity = _make_actor(game, "角色.无名")
        game.get_agent_memory(entity).messages.append(
            HumanMessage(content="loop 起点", loop_id="play_cards:1:x#1")
        )

        save_dir = tmp_path / "snap"
        assert world_persistence.save_world(
            game._world, game._player_session, tmp_path, save_dir
        )


#######################################################################################################
# AgentMemory 直写同样受闸门保护（与 agent_loop 的写入方式一致）
#######################################################################################################
def test_agent_memory_direct_write_is_checked_at_save(
    sample_game: Any, tmp_path: Path
) -> None:
    world = sample_game._world
    world.agent_memories["世界.导演"] = AgentMemory(
        name="世界.导演", messages=[HumanMessage(content="x", bad="1")]
    )

    with pytest.raises(AssertionError, match="未登记的记忆标记"):
        world_persistence.save_world(
            world, sample_game._player_session, tmp_path, tmp_path / "snap"
        )
