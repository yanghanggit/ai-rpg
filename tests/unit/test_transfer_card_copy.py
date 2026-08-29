"""针对 PlayCardsActionSystem._transfer_card_copy（可传递卡牌 copy 到目标手牌）的单元测试。"""

from typing import Any, cast

from src.ai_rpg.entitas.entity import Entity
from src.ai_rpg.game.dbg_game import DBGGame
from src.ai_rpg.models import (
    ActorComponent,
    Blueprint,
    Card,
    DeathComponent,
    Dungeon,
    HandComponent,
    PlayerSession,
    TargetType,
    WorldState,
)
from src.ai_rpg.systems.play_cards_action_system import PlayCardsActionSystem


def _make_game() -> DBGGame:
    blueprint = Blueprint(
        name="test",
        player_actor="hero",
        campaign_setting="",
        knowledge_base={},
        stages=[],
        world_entities=[],
        storage_entity="世界储物箱",
    )
    world = WorldState(
        entity_counter=0,
        entities=[],
        agent_memories={},
        dungeon=Dungeon(name="d", rooms=[], profile=""),
        blueprint=blueprint,
    )
    session = PlayerSession(name="player", actor="hero", game="test")
    return DBGGame(name="test", player_session=session, world=world)


def _make_actor(game: Any, name: str, stage_name: str) -> Entity:
    entity: Entity = cast(Entity, game._create_entity(name))
    entity.add(ActorComponent, name, stage_name)
    entity.add(HandComponent, name, [])
    return entity


def _make_card() -> Card:
    return Card(
        name="蚀纸毒",
        description="测试毒牌",
        transferable=True,
        retain=True,
        damage=1,
        hit_count=1,
        target_type=TargetType.SINGLE,
        self_target=False,
        source="角色.无名",
    )


class TestTransferCardCopy:
    def test_copies_to_each_alive_target_with_new_uuid(self) -> None:
        game = _make_game()
        system = PlayCardsActionSystem(game)
        a = _make_actor(game, "怪物.甲", "stage1")
        b = _make_actor(game, "怪物.乙", "stage1")
        card = _make_card()
        original_uuid = card.uuid

        count = system._transfer_card_copy(card, ["怪物.甲", "怪物.乙"])

        assert count == 2
        for target in (a, b):
            hand = target.get(HandComponent).cards
            assert len(hand) == 1
            copied = hand[0]
            assert copied.name == "蚀纸毒"
            assert copied.source == "角色.无名"
            assert copied.transferable is True
            assert copied.uuid != original_uuid
            assert copied is not card
        # 原卡自身不被修改
        assert card.uuid == original_uuid

    def test_skips_dead_and_missing_target(self) -> None:
        game = _make_game()
        system = PlayCardsActionSystem(game)
        alive = _make_actor(game, "怪物.甲", "stage1")
        dead = _make_actor(game, "怪物.乙", "stage1")
        dead.add(DeathComponent, "怪物.乙")

        count = system._transfer_card_copy(
            _make_card(), ["怪物.甲", "怪物.乙", "不存在的人"]
        )

        assert count == 1
        assert len(alive.get(HandComponent).cards) == 1
        assert len(dead.get(HandComponent).cards) == 0

    def test_dedups_repeated_targets(self) -> None:
        game = _make_game()
        system = PlayCardsActionSystem(game)
        a = _make_actor(game, "怪物.甲", "stage1")

        count = system._transfer_card_copy(_make_card(), ["怪物.甲", "怪物.甲"])

        assert count == 1
        assert len(a.get(HandComponent).cards) == 1
