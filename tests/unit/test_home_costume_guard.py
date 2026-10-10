"""时装操作对失能角色的守卫测试。

确认 activate_wear_costume / activate_remove_costume 拒绝已永久失能
（IncapacitatedComponent）的角色，避免其外观被更新、进而产生记忆写入。
"""

from typing import Tuple
from unittest.mock import MagicMock

import pytest

from ai_rpg.entitas.context import Context
from ai_rpg.entitas.entity import Entity
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import (
    ActorComponent,
    AppearanceComponent,
    IncapacitatedComponent,
    RemoveCostumeAction,
    StorageComponent,
    WearCostumeAction,
)
from ai_rpg.services.home_actions import (
    activate_remove_costume,
    activate_wear_costume,
)


@pytest.fixture()
def context() -> Context:
    return Context()


def _setup(context: Context, *, incapacitated: bool) -> Tuple[MagicMock, Entity]:
    """构造一个带储物箱与家园目标角色的 mock game。"""
    game = MagicMock(spec=DBGGame)

    storage = context.create_entity()
    storage._name = "世界.储物箱"
    storage.add(StorageComponent, "世界.储物箱", [])
    game.get_storage_entity.return_value = storage

    target = context.create_entity()
    target._name = "角色.NPC_A"
    target.add(ActorComponent, "角色.NPC_A", "场景.家园")
    target.add(AppearanceComponent, "角色.NPC_A", "基础体型", "基础体型")
    if incapacitated:
        target.add(IncapacitatedComponent, "角色.NPC_A")
    game.get_actor_entity.return_value = target

    return game, target


def test_activate_wear_costume_rejects_incapacitated(context: Context) -> None:
    """失能角色不允许被穿上时装。"""
    game, target = _setup(context, incapacitated=True)

    success, error_detail = activate_wear_costume(game, "时装.铁甲", "角色.NPC_A")

    assert success is False
    assert "失能" in error_detail
    assert not target.has(WearCostumeAction)


def test_activate_remove_costume_rejects_incapacitated(context: Context) -> None:
    """失能角色不允许被脱下时装。"""
    game, target = _setup(context, incapacitated=True)

    success, error_detail = activate_remove_costume(game, "角色.NPC_A")

    assert success is False
    assert "失能" in error_detail
    assert not target.has(RemoveCostumeAction)
