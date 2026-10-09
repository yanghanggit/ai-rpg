"""ECS ↔ 存储契约测试。

护栏一（Step 1）：entitas 核心的句柄 / pools 语义不变。
护栏二（Stage C）：name-keyed 的 ``serialize_context`` / ``restore_context``
与 ``world_persistence`` 之间的接口契约。
"""

import json
import uuid
from typing import Iterator

import pytest

from ai_rpg.entitas import Component, Entity
from ai_rpg.game.rpg_entity_manager import RPGEntityManager
from ai_rpg.models import (
    COMPONENT_TYPES,
    IdentityComponent,
    create_component_type,
)


@pytest.fixture(autouse=True)
def _clean_dynamic_component_types() -> Iterator[None]:
    before = set(COMPONENT_TYPES.keys())
    yield
    for key in list(COMPONENT_TYPES.keys()):
        if key not in before:
            del COMPONENT_TYPES[key]


def _new_id() -> str:
    return str(uuid.uuid4())


class TestContextDataSerialization:
    def test_serialize_context_orders_by_slot_index(self) -> None:
        source = RPGEntityManager()
        first = source._create_entity("first")
        first.add(IdentityComponent, "first", 9, _new_id())
        second = source._create_entity("second")
        second.add(IdentityComponent, "second", 2, _new_id())

        data = source.serialize_context()

        # 按 slot index（即创建顺序）导出，与 creation_order 字段无关
        assert list(data) == ["first", "second"]

    def test_destroyed_entity_is_not_serialized(self) -> None:
        manager = RPGEntityManager()

        dead = manager._create_entity("dead")
        dead.add(IdentityComponent, "dead", 1, _new_id())
        manager.destroy_entity(dead)

        live = manager._create_entity("live")
        live.add(IdentityComponent, "live", 2, _new_id())

        data = manager.serialize_context()

        assert list(data) == ["live"]

    def test_serialization_reads_components_via_public_api(self) -> None:
        manager = RPGEntityManager()
        entity = manager._create_entity("probe")
        entity.add(IdentityComponent, "probe", 1, _new_id())

        items = entity.iter_component_items()
        assert [comp_type for comp_type, _ in items] == list(entity.component_types)
        assert entity.get_all_components() == tuple(comp for _, comp in items)


class TestNameIndexContract:
    def test_name_lookup_and_cleanup_on_destroy(self) -> None:
        manager = RPGEntityManager()
        entity = manager._create_entity("keeper")
        entity.add(IdentityComponent, "keeper", 1, _new_id())

        assert manager.get_entity_by_name("keeper") == entity

        manager.destroy_entity(entity)
        assert manager.get_entity_by_name("keeper") is None

    def test_recreated_name_points_to_new_handle(self) -> None:
        manager = RPGEntityManager()
        first = manager._create_entity("node")
        first.add(IdentityComponent, "node", 1, _new_id())
        manager.destroy_entity(first)

        second = manager._create_entity("node")
        second.add(IdentityComponent, "node", 2, _new_id())

        assert manager.get_entity_by_name("node") == second
        assert manager.get_entity_by_name("node") != first


class TestIndexHandleContract:
    def test_context_entities_property_is_a_set_of_handles(self) -> None:
        manager = RPGEntityManager()
        entity = manager._create_entity("solo")
        entity.add(IdentityComponent, "solo", 1, _new_id())

        assert isinstance(manager.entities, set)
        assert entity in manager.entities

    def test_group_entities_support_copy_for_safe_iteration(self) -> None:
        from ai_rpg.entitas import Matcher

        manager = RPGEntityManager()
        entity = manager._create_entity("iter")
        entity.add(IdentityComponent, "iter", 1, _new_id())

        group = manager.get_group(Matcher(IdentityComponent))
        snapshot = group.entities.copy()
        # 修改世界不应影响快照
        manager.destroy_entity(entity)
        assert entity in snapshot
        assert entity not in group.entities

    def test_entity_handle_hashable_and_usable_in_sets(self) -> None:
        manager = RPGEntityManager()
        entity = manager._create_entity("hash")
        entity.add(IdentityComponent, "hash", 1, _new_id())

        assert {entity} == {entity}
        assert isinstance(entity, Entity)


class TestContextSnapshotContract:
    """Stage B 护栏：name-keyed 的 serialize_context / restore_context。"""

    def test_context_snapshot_round_trip(self) -> None:
        tag_cls = create_component_type("SnapshotTag", value=(int, ...))

        source = RPGEntityManager()
        hero = source._create_entity("hero")
        hero.add(IdentityComponent, "hero", 1, _new_id())

        goblin = source._create_entity("goblin")
        goblin.add(IdentityComponent, "goblin", 2, _new_id())
        goblin.set(tag_cls, tag_cls.model_validate({"value": 7}))

        data = source.serialize_context()
        assert list(data) == ["hero", "goblin"]
        assert data["goblin"][tag_cls.__name__] == {"value": 7}

        # 走一遍 JSON（模拟落盘再读回）
        reloaded = json.loads(json.dumps(data))

        target = RPGEntityManager()
        restored = target.restore_context(reloaded)

        assert set(restored) == {"hero", "goblin"}
        assert target.get_entity_by_name("hero") is restored["hero"]
        assert restored["hero"].get(IdentityComponent).creation_order == 1
        assert restored["goblin"].get(tag_cls).model_dump() == {"value": 7}

    def test_serialize_context_skips_unregistered_components(self) -> None:
        class Unregistered(Component):
            value: int

        manager = RPGEntityManager()
        entity = manager._create_entity("probe")
        entity.add(IdentityComponent, "probe", 1, _new_id())
        entity.set(Unregistered, Unregistered(value=1))

        data = manager.serialize_context()

        assert "Unregistered" not in data["probe"]
        assert "IdentityComponent" in data["probe"]

    def test_restore_context_requires_empty_context(self) -> None:
        manager = RPGEntityManager()
        existing = manager._create_entity("existing")
        existing.add(IdentityComponent, "existing", 1, _new_id())

        with pytest.raises(AssertionError, match="empty context"):
            manager.restore_context({})
