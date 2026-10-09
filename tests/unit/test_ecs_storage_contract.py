"""ECS ↔ 存储契约测试（Step 1 的护栏）。

这一步只重构了 entitas 核心（entity 变句柄、组件存入 context pools），存储流程
（``world_persistence`` / ``RPGEntityManager.serialize_entities``）保持不变。本文件
锁定二者之间的接口契约，确保后续再动存储时不会悄悄破坏现有流程。
"""

import uuid
from typing import Iterator

import pytest

from ai_rpg.entitas import Entity
from ai_rpg.game.rpg_entity_manager import RPGEntityManager
from ai_rpg.models import (
    COMPONENT_TYPES,
    EntitySerialization,
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


class TestSerializeDeserializeContract:
    def test_round_trip_through_entity_serialization(self) -> None:
        tag_cls = create_component_type("ContractTag", value=(int, ...))

        source = RPGEntityManager()
        hero = source._create_entity("hero")
        hero.add(IdentityComponent, "hero", 1, _new_id())

        goblin = source._create_entity("goblin")
        goblin.add(IdentityComponent, "goblin", 2, _new_id())
        goblin.set(tag_cls, tag_cls.model_validate({"value": 7}))

        serialized = source.serialize_entities(source.entities)
        assert [s.name for s in serialized] == ["hero", "goblin"]

        # world_persistence 会先落成 JSON 再读回，这里模拟同样的往返。
        raws = [s.model_dump_json() for s in serialized]
        reloaded = [EntitySerialization.model_validate_json(raw) for raw in raws]

        target = RPGEntityManager()
        restored = target.deserialize_entities(reloaded)
        by_name = {entity.name: entity for entity in restored}

        assert by_name["hero"].get(IdentityComponent).creation_order == 1
        assert by_name["goblin"].has(tag_cls)
        assert by_name["goblin"].get(tag_cls).model_dump() == {"value": 7}

    def test_serialize_sorts_by_creation_order(self) -> None:
        source = RPGEntityManager()
        late = source._create_entity("late")
        late.add(IdentityComponent, "late", 9, _new_id())
        early = source._create_entity("early")
        early.add(IdentityComponent, "early", 2, _new_id())

        serialized = source.serialize_entities(source.entities)
        assert [s.name for s in serialized] == ["early", "late"]

    def test_destroyed_entity_is_not_serialized(self) -> None:
        manager = RPGEntityManager()

        dead = manager._create_entity("dead")
        dead.add(IdentityComponent, "dead", 1, _new_id())
        manager.destroy_entity(dead)

        live = manager._create_entity("live")
        live.add(IdentityComponent, "live", 2, _new_id())

        serialized = manager.serialize_entities(manager.entities)
        assert [s.name for s in serialized] == ["live"]

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
