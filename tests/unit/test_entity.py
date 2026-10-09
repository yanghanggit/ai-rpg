"""
Tests for the Entity handle in the entitas framework.

Entities are lightweight handles: component data lives in the owning
context's pools, and the handle only carries ``(store, index, version)``.
Every entity is created through a :class:`Context`.
"""

from typing import Set, Type
from unittest.mock import Mock

import pytest

from ai_rpg.entitas import Context, Entity
from ai_rpg.entitas.components import Component
from ai_rpg.entitas.exceptions import (
    AlreadyAddedComponent,
    EntityNotEnabled,
    MissingComponent,
)
from ecs_testing import (
    Health,
    Marker,
    Name,
    Position,
    Transform,
    Velocity,
)


@pytest.fixture
def context() -> Context:
    return Context()


@pytest.fixture
def entity(context: Context) -> Entity:
    return context.create_entity()


class TestEntityLifecycle:
    def test_entity_initialization(self, entity: Entity) -> None:
        assert entity.is_enabled
        assert entity.index == 0
        assert entity.name == ""
        assert entity.component_count == 0

        assert entity.on_component_added is not None
        assert entity.on_component_removed is not None
        assert entity.on_component_replaced is not None

    def test_index_is_dense_and_monotonic(self, context: Context) -> None:
        first = context.create_entity()
        second = context.create_entity()
        third = context.create_entity()

        assert (first.index, second.index, third.index) == (0, 1, 2)

    def test_destroy_disables_entity(self, context: Context, entity: Entity) -> None:
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)

        context.destroy_entity(entity)

        assert not entity.is_enabled
        assert entity.component_count == 0


class TestComponentOperations:
    def test_add_component_success(self, entity: Entity) -> None:
        entity.on_component_added = Mock()

        entity.add(Position, 10, 20)

        assert entity.has(Position)
        pos_comp = entity.get(Position)
        assert pos_comp.x == 10
        assert pos_comp.y == 20
        entity.on_component_added.assert_called_once()

    def test_add_component_to_disabled_entity(
        self, context: Context, entity: Entity
    ) -> None:
        context.destroy_entity(entity)

        with pytest.raises(EntityNotEnabled):
            entity.add(Position, 10, 20)

    def test_add_duplicate_component(self, entity: Entity) -> None:
        entity.add(Position, 10, 20)

        with pytest.raises(AlreadyAddedComponent):
            entity.add(Position, 30, 40)

    def test_remove_component_success(self, entity: Entity) -> None:
        entity.add(Position, 10, 20)

        entity.on_component_removed = Mock()
        entity.remove(Position)

        assert not entity.has(Position)
        entity.on_component_removed.assert_called_once()

    def test_remove_component_from_disabled_entity(
        self, context: Context, entity: Entity
    ) -> None:
        entity.add(Position, 10, 20)
        context.destroy_entity(entity)

        with pytest.raises(EntityNotEnabled):
            entity.remove(Position)

    def test_remove_nonexistent_component(self, entity: Entity) -> None:
        with pytest.raises(MissingComponent):
            entity.remove(Position)

    def test_replace_existing_component(self, entity: Entity) -> None:
        entity.add(Position, 10, 20)

        entity.on_component_replaced = Mock()
        entity.replace(Position, 30, 40)

        assert entity.get(Position).x == 30
        assert entity.get(Position).y == 40
        entity.on_component_replaced.assert_called_once()

    def test_replace_nonexistent_component_adds_it(self, entity: Entity) -> None:
        entity.on_component_added = Mock()
        entity.replace(Position, 10, 20)

        assert entity.has(Position)
        assert entity.get(Position).x == 10
        entity.on_component_added.assert_called_once()

    def test_replace_component_on_disabled_entity(
        self, context: Context, entity: Entity
    ) -> None:
        context.destroy_entity(entity)

        with pytest.raises(EntityNotEnabled):
            entity.replace(Position, 10, 20)

    def test_get_nonexistent_component(self, entity: Entity) -> None:
        with pytest.raises(MissingComponent):
            entity.get(Position)

    def test_get_after_destroy_raises_missing(
        self, context: Context, entity: Entity
    ) -> None:
        entity.add(Position, 1, 2)
        context.destroy_entity(entity)

        with pytest.raises(MissingComponent):
            entity.get(Position)

    def test_has_and_has_any(self, entity: Entity) -> None:
        assert not entity.has(Position)

        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)

        assert entity.has(Position)
        assert entity.has(Position, Velocity)
        assert not entity.has(Position, Velocity, Health)

        assert entity.has_any(Position, Velocity)
        assert entity.has_any(Velocity, Position)
        assert not entity.has_any(Health, Name)

    def test_remove_all_components(self, entity: Entity) -> None:
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)
        entity.add(Health, 100, 100)

        entity.remove_all()

        assert not entity.has(Position)
        assert not entity.has(Velocity)
        assert not entity.has(Health)
        assert entity.component_count == 0

    def test_set_component_instance(self, entity: Entity) -> None:
        entity.on_component_added = Mock()

        pos_comp = Position(x=10, y=20)
        entity.set(Position, pos_comp)

        assert entity.has(Position)
        assert entity.get(Position) == pos_comp
        entity.on_component_added.assert_called_once_with(entity, pos_comp)

    def test_set_on_disabled_entity(self, context: Context, entity: Entity) -> None:
        context.destroy_entity(entity)

        with pytest.raises(EntityNotEnabled):
            entity.set(Position, Position(x=10, y=20))

    def test_set_duplicate_component(self, entity: Entity) -> None:
        entity.set(Position, Position(x=10, y=20))

        with pytest.raises(AlreadyAddedComponent):
            entity.set(Position, Position(x=30, y=40))

    def test_component_with_no_fields(self, entity: Entity) -> None:
        entity.add(Marker)

        assert entity.has(Marker)
        assert entity.get(Marker) == Marker()

    def test_component_with_many_fields(self, entity: Entity) -> None:
        entity.add(Transform, 10, 20, 45, 1.5)

        transform_comp = entity.get(Transform)
        assert transform_comp.x == 10
        assert transform_comp.y == 20
        assert transform_comp.rotation == 45
        assert transform_comp.scale == 1.5


class TestEntityEvents:
    def test_event_callbacks(self, entity: Entity) -> None:
        added_callback = Mock()
        removed_callback = Mock()
        replaced_callback = Mock()

        entity.on_component_added += added_callback
        entity.on_component_removed += removed_callback
        entity.on_component_replaced += replaced_callback

        entity.add(Position, 10, 20)
        added_callback.assert_called_once()

        entity.replace(Position, 30, 40)
        replaced_callback.assert_called_once()

        entity.remove(Position)
        removed_callback.assert_called_once()


class TestEntityIntrospection:
    def test_component_introspection(self, entity: Entity) -> None:
        entity.add(Position, 1, 2)
        entity.add(Velocity, 3, 4)

        assert entity.component_count == 2
        expected: Set[Type[Component]] = {Position, Velocity}
        assert set(entity.component_types) == expected
        assert len(entity.get_all_components()) == 2
        assert set(dict(entity.iter_component_items()).keys()) == expected

    def test_entity_repr(self, entity: Entity) -> None:
        assert "Entity_0" in str(entity)

        entity.add(Position, 10, 20)
        entity.add(Name, "Player")

        repr_str = str(entity)
        assert "Entity_0" in repr_str
        assert "Position" in repr_str or "Name" in repr_str

    def test_components_are_isolated_per_entity(self, context: Context) -> None:
        first = context.create_entity()
        second = context.create_entity()

        first.add(Position, 1, 1)
        second.add(Position, 2, 2)

        assert first.get(Position).x == 1
        assert second.get(Position).x == 2
        assert first != second

    def test_equality_is_stable_for_same_handle(self, entity: Entity) -> None:
        assert entity == entity
        assert {entity} == {entity}

    def test_entities_from_different_contexts_are_distinct(self) -> None:
        first = Context().create_entity()
        second = Context().create_entity()

        assert first != second
        assert len({first, second}) == 2

    def test_destroyed_handle_is_disabled_and_distinct(self, context: Context) -> None:
        stale = context.create_entity()
        context.destroy_entity(stale)

        fresh = context.create_entity()

        assert not stale.is_enabled
        assert fresh.is_enabled
        assert fresh.index != stale.index  # slots are never recycled
        assert fresh != stale

        with pytest.raises(EntityNotEnabled):
            stale.add(Position, 1, 2)
