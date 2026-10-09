"""entitas 核心 dump / load 单元测试（Stage A 护栏）。

Stage A 让 entitas 自己定义 name-keyed 的 ``ContextData`` 表示与
``dump_*`` / ``load_context``，且不依赖 ``models.registry``：组件类型解析靠注入的
``ComponentResolver``。本文件锁定该核心行为，确保后续接入存档时不被破坏。
"""

import json
from typing import Dict, List, Tuple, Type

import pytest

from ai_rpg.entitas import (
    Component,
    ComponentData,
    Context,
    ContextData,
    Matcher,
    dump_context,
    dump_entities,
    dump_entity,
    load_context,
)
from ecs_testing import Health, Marker, Name, Position, Transform, Velocity

_RESOLVERS: Dict[str, Type[Component]] = {
    Position.__name__: Position,
    Velocity.__name__: Velocity,
    Health.__name__: Health,
    Name.__name__: Name,
    Marker.__name__: Marker,
    Transform.__name__: Transform,
}


def _resolve(name: str, data: ComponentData) -> Type[Component]:
    return _RESOLVERS[name]


class TestDump:
    def test_dump_context_is_name_keyed(self) -> None:
        context = Context()
        hero = context.create_entity()
        hero.name = "hero"
        hero.add(Position, 1.0, 2.0)

        data = dump_context(context)

        assert set(data) == {"hero"}
        assert data["hero"]["Position"] == {"x": 1.0, "y": 2.0}

    def test_dump_context_orders_by_slot_index(self) -> None:
        context = Context()
        first = context.create_entity()
        first.name = "first"
        second = context.create_entity()
        second.name = "second"

        assert list(dump_context(context)) == ["first", "second"]

    def test_dump_entity_returns_component_data(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.name = "e"
        entity.add(Position, 1.0, 2.0)
        entity.add(Marker)

        assert dump_entity(entity) == {"Position": {"x": 1.0, "y": 2.0}, "Marker": {}}

    def test_component_filter_skips_types(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.name = "e"
        entity.add(Position, 1.0, 2.0)
        entity.add(Velocity, 3.0, 4.0)

        data = dump_entities([entity], component_filter=lambda t: t is not Velocity)

        assert data["e"] == {"Position": {"x": 1.0, "y": 2.0}}

    def test_duplicate_name_raises(self) -> None:
        context = Context()
        first = context.create_entity()
        first.name = "dup"
        second = context.create_entity()
        second.name = "dup"

        with pytest.raises(AssertionError, match="Duplicate entity name"):
            dump_context(context)

    def test_unnamed_entity_raises(self) -> None:
        context = Context()
        context.create_entity()

        with pytest.raises(AssertionError, match="has no name"):
            dump_context(context)


class TestLoad:
    def test_round_trip_rebuilds_core(self) -> None:
        source = Context()
        hero = source.create_entity()
        hero.name = "hero"
        hero.add(Position, 1.0, 2.0)
        hero.add(Health, 10, 20)
        goblin = source.create_entity()
        goblin.name = "goblin"
        goblin.add(Transform, 1.0, 2.0, 3.0, 4.0)

        target = Context()
        restored = load_context(target, dump_context(source), _resolve)

        assert set(restored) == {"hero", "goblin"}
        assert restored["hero"].name == "hero"
        assert restored["hero"].get(Position) == Position(x=1.0, y=2.0)
        assert restored["hero"].get(Health) == Health(value=10, max_value=20)
        assert restored["goblin"].has(Transform)
        assert target.entity_count == 2

    def test_json_round_trip(self) -> None:
        source = Context()
        entity = source.create_entity()
        entity.name = "e"
        entity.add(Position, 1.5, 2.5)

        raw = json.dumps(dump_context(source))
        data: ContextData = json.loads(raw)

        target = Context()
        restored = load_context(target, data, _resolve)

        assert restored["e"].get(Position) == Position(x=1.5, y=2.5)

    def test_load_into_non_empty_context_raises(self) -> None:
        target = Context()
        existing = target.create_entity()
        existing.name = "existing"

        with pytest.raises(AssertionError, match="empty context"):
            load_context(target, {}, _resolve)

    def test_load_bypasses_component_events(self) -> None:
        # 分组在 load 之前创建；load 直接写 storage、不触发组件事件，
        # 因此预先存在的分组不会被更新（分组应在 load 之后再创建）。
        target = Context()
        group = target.get_group(Matcher(Position))

        source = Context()
        entity = source.create_entity()
        entity.name = "e"
        entity.add(Position, 1.0, 2.0)

        load_context(target, dump_context(source), _resolve)

        assert group.entity_count == 0
        assert target.entity_count == 1

    def test_resolver_receives_name_and_data(self) -> None:
        calls: List[Tuple[str, ComponentData]] = []

        def resolver(name: str, data: ComponentData) -> Type[Component]:
            calls.append((name, data))
            return _RESOLVERS[name]

        target = Context()
        load_context(target, {"e": {"Position": {"x": 1.0, "y": 2.0}}}, resolver)

        assert calls == [("Position", {"x": 1.0, "y": 2.0})]

    def test_empty_context_round_trips(self) -> None:
        assert load_context(Context(), dump_context(Context()), _resolve) == {}
