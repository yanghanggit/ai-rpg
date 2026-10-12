"""队伍名单守卫测试。

确认 add_party_member 对正常 NPC 的行为（回归保护）。
"""

from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    NPCComponent,
    PartyRosterComponent,
)
from ai_rpg.services.home_actions import add_party_member


@pytest.fixture()
def context() -> Context:
    return Context()


def test_add_party_member_accepts_healthy_npc(context: Context) -> None:
    """正常 NPC 可以加入队伍名单（回归保护）。"""
    game = MagicMock(spec=DBGGame)

    member = context.create_entity()
    member._name = "角色.NPC_A"
    member.add(ActorComponent, "角色.NPC_A", "场景.家园")
    member.add(NPCComponent, "角色.NPC_A")

    player = context.create_entity()
    player._name = "角色.玩家"

    game.get_actor_entity.return_value = member
    game.get_player_entity.return_value = player

    success, error_detail = add_party_member(game, "角色.NPC_A")

    assert success is True
    assert error_detail == ""
    assert player.has(PartyRosterComponent)
    assert list(player.get(PartyRosterComponent).members) == ["角色.NPC_A"]
