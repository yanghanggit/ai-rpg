"""
Tests for the Entity class in entitas framework.
"""

import pytest
from unittest.mock import Mock, call

from src.multi_agents_game.entitas import Entity
from src.multi_agents_game.entitas.exceptions import (
    EntityNotEnabled,
    AlreadyAddedComponent,
    MissingComponent,
)
from tests.unit.test_components import (
    Position,
    Velocity,
    Health,
    Name,
    Marker,
    Transform,
)


class TestEntity:
    """Test cases for Entity class."""

    def test_entity_initialization(self) -> None:
        """Test that entity is properly initialized."""
        entity = Entity()

        # Entity should not be enabled initially
        assert not entity._is_enabled
        assert entity._creation_index == 0
        assert entity._name == ""
        assert len(entity._components) == 0

        # Events should be initialized
        assert entity.on_component_added is not None
        assert entity.on_component_removed is not None
        assert entity.on_component_replaced is not None

    def test_entity_activation(self) -> None:
        """Test entity activation."""
        entity = Entity()
        creation_index = 42

        entity.activate(creation_index)

        assert entity._is_enabled
        assert entity._creation_index == creation_index

    def test_add_component_success(self) -> None:
        """Test successfully adding a component."""
        entity = Entity()
        entity.activate(1)

        # Mock the event
        entity.on_component_added = Mock()

        entity.add(Position, 10, 20)

        assert entity.has(Position)
        pos_comp = entity.get(Position)
        assert pos_comp.x == 10
        assert pos_comp.y == 20

        # Event should be called
        entity.on_component_added.assert_called_once()

    def test_add_component_to_disabled_entity(self) -> None:
        """Test that adding component to disabled entity raises exception."""
        entity = Entity()
        # Don't activate the entity

        with pytest.raises(EntityNotEnabled):
            entity.add(Position, 10, 20)

    def test_add_duplicate_component(self) -> None:
        """Test that adding duplicate component raises exception."""
        entity = Entity()
        entity.activate(1)

        entity.add(Position, 10, 20)

        with pytest.raises(AlreadyAddedComponent):
            entity.add(Position, 30, 40)

    def test_remove_component_success(self) -> None:
        """Test successfully removing a component."""
        entity = Entity()
        entity.activate(1)

        # Add component first
        entity.add(Position, 10, 20)

        # Mock the event
        entity.on_component_removed = Mock()

        entity.remove(Position)

        assert not entity.has(Position)
        # Event should be called
        entity.on_component_removed.assert_called_once()

    def test_remove_component_from_disabled_entity(self) -> None:
        """Test that removing component from disabled entity raises exception."""
        entity = Entity()
        entity.activate(1)
        entity.add(Position, 10, 20)

        # Disable entity
        entity._is_enabled = False

        with pytest.raises(EntityNotEnabled):
            entity.remove(Position)

    def test_remove_nonexistent_component(self) -> None:
        """Test that removing non-existent component raises exception."""
        entity = Entity()
        entity.activate(1)

        with pytest.raises(MissingComponent):
            entity.remove(Position)

    def test_replace_existing_component(self) -> None:
        """Test replacing an existing component."""
        entity = Entity()
        entity.activate(1)

        # Add component first
        entity.add(Position, 10, 20)

        # Mock the event
        entity.on_component_replaced = Mock()

        entity.replace(Position, 30, 40)

        assert entity.has(Position)
        pos_comp = entity.get(Position)
        assert pos_comp.x == 30
        assert pos_comp.y == 40

        # Event should be called
        entity.on_component_replaced.assert_called_once()

    def test_replace_nonexistent_component(self) -> None:
        """Test replacing non-existent component adds it instead."""
        entity = Entity()
        entity.activate(1)

        # Mock the event
        entity.on_component_added = Mock()

        entity.replace(Position, 10, 20)

        assert entity.has(Position)
        pos_comp = entity.get(Position)
        assert pos_comp.x == 10
        assert pos_comp.y == 20

        # Add event should be called instead of replace
        entity.on_component_added.assert_called_once()

    def test_replace_component_on_disabled_entity(self) -> None:
        """Test that replacing component on disabled entity raises exception."""
        entity = Entity()
        # Don't activate the entity

        with pytest.raises(EntityNotEnabled):
            entity.replace(Position, 10, 20)

    def test_get_component_success(self) -> None:
        """Test successfully getting a component."""
        entity = Entity()
        entity.activate(1)

        entity.add(Position, 10, 20)
        pos_comp = entity.get(Position)

        assert pos_comp.x == 10
        assert pos_comp.y == 20

    def test_get_nonexistent_component(self) -> None:
        """Test getting non-existent component raises exception."""
        entity = Entity()
        entity.activate(1)

        with pytest.raises(MissingComponent):
            entity.get(Position)

    def test_has_single_component(self) -> None:
        """Test checking if entity has a single component."""
        entity = Entity()
        entity.activate(1)

        assert not entity.has(Position)

        entity.add(Position, 10, 20)
        assert entity.has(Position)

    def test_has_multiple_components(self) -> None:
        """Test checking if entity has multiple components."""
        entity = Entity()
        entity.activate(1)

        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)

        assert entity.has(Position, Velocity)
        assert not entity.has(Position, Velocity, Health)

    def test_has_any_components(self) -> None:
        """Test checking if entity has any of the specified components."""
        entity = Entity()
        entity.activate(1)

        entity.add(Position, 10, 20)

        assert entity.has_any(Position, Velocity)
        assert entity.has_any(Velocity, Position)
        assert not entity.has_any(Velocity, Health)

    def test_remove_all_components(self) -> None:
        """Test removing all components from entity."""
        entity = Entity()
        entity.activate(1)

        # Add multiple components
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)
        entity.add(Health, 100, 100)

        entity.remove_all()

        assert not entity.has(Position)
        assert not entity.has(Velocity)
        assert not entity.has(Health)
        assert len(entity._components) == 0

    def test_destroy_entity(self) -> None:
        """Test destroying an entity."""
        entity = Entity()
        entity.activate(1)

        # Add some components
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)

        entity.destroy()

        assert not entity._is_enabled
        assert len(entity._components) == 0

    def test_entity_repr(self) -> None:
        """Test entity string representation."""
        entity = Entity()
        entity.activate(5)

        # Empty entity
        assert "Entity_5" in str(entity)

        # Entity with components
        entity.add(Position, 10, 20)
        entity.add(Name, "Player")

        repr_str = str(entity)
        assert "Entity_5" in repr_str
        assert "Position" in repr_str or "Name" in repr_str

    def test_insert_component_success(self) -> None:
        """Test successfully inserting a component object."""
        entity = Entity()
        entity.activate(1)

        # Mock the event
        entity.on_component_added = Mock()

        # Create component object directly
        pos_comp = Position(x=10, y=20)
        entity.set(Position, pos_comp)

        assert entity.has(Position)
        acquired_position_component = entity.get(Position)
        assert acquired_position_component == pos_comp

        # Event should be called
        entity.on_component_added.assert_called_once_with(entity, pos_comp)

    def test_insert_component_to_disabled_entity(self) -> None:
        """Test that inserting component to disabled entity raises exception."""
        entity = Entity()
        # Don't activate the entity

        pos_comp = Position(x=10, y=20)

        with pytest.raises(EntityNotEnabled):
            entity.set(Position, pos_comp)

    def test_insert_duplicate_component(self) -> None:
        """Test that inserting duplicate component raises exception."""
        entity = Entity()
        entity.activate(1)

        pos_comp1 = Position(x=10, y=20)
        pos_comp2 = Position(x=30, y=40)

        entity.set(Position, pos_comp1)

        with pytest.raises(AlreadyAddedComponent):
            entity.set(Position, pos_comp2)

    def test_component_with_no_fields(self) -> None:
        """Test component with no fields (edge case)."""
        entity = Entity()
        entity.activate(1)

        entity.add(Marker)

        assert entity.has(Marker)
        marker_comp = entity.get(Marker)
        assert marker_comp == Marker()

    def test_component_with_many_fields(self) -> None:
        """Test component with multiple fields."""
        entity = Entity()
        entity.activate(1)

        entity.add(Transform, 10, 20, 45, 1.5)

        assert entity.has(Transform)
        transform_comp = entity.get(Transform)
        assert transform_comp.x == 10
        assert transform_comp.y == 20
        assert transform_comp.rotation == 45
        assert transform_comp.scale == 1.5

    def test_event_callbacks(self) -> None:
        """Test that events are properly triggered."""
        entity = Entity()
        entity.activate(1)

        # Create mock callbacks
        added_callback = Mock()
        removed_callback = Mock()
        replaced_callback = Mock()

        # Register callbacks
        entity.on_component_added += added_callback
        entity.on_component_removed += removed_callback
        entity.on_component_replaced += replaced_callback

        # Add component
        entity.add(Position, 10, 20)
        added_callback.assert_called_once()

        # Replace component
        entity.replace(Position, 30, 40)
        replaced_callback.assert_called_once()

        # Remove component
        entity.remove(Position)
        removed_callback.assert_called_once()

    def test_entity_state_consistency(self) -> None:
        """Test that entity maintains consistent state through operations."""
        entity = Entity()
        entity.activate(1)

        # Initial state
        assert entity._is_enabled
        assert len(entity._components) == 0

        # Add components
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)
        assert len(entity._components) == 2

        # Replace one component
        entity.replace(Position, 30, 40)
        assert len(entity._components) == 2
        assert entity.get(Position).x == 30

        # Remove one component
        entity.remove(Velocity)
        assert len(entity._components) == 1
        assert entity.has(Position)
        assert not entity.has(Velocity)

        # Destroy entity
        entity.destroy()
        assert not entity._is_enabled
        assert len(entity._components) == 0
