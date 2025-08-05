"""
Tests for the Context class in entitas framework.
"""

import pytest
from unittest.mock import Mock, patch

from src.multi_agents_game.entitas import Context, Entity, Matcher, Group
from src.multi_agents_game.entitas.exceptions import MissingEntity
from tests.unit.test_components import Position, Velocity, Health, Name, Age


class TestContext:
    """Test cases for Context class."""

    def test_context_initialization(self) -> None:
        """Test that context is properly initialized."""
        context = Context()

        assert len(context._entities) == 0
        assert len(context._reusable_entities) == 0
        assert context._entity_index == 0
        assert len(context._groups) == 0

    def test_create_entity(self) -> None:
        """Test creating a new entity."""
        context = Context()

        entity = context.create_entity()

        assert entity is not None
        assert entity._is_enabled
        assert entity._creation_index == 0
        assert context._entity_index == 1
        assert len(context._entities) == 1
        assert entity in context._entities

    def test_create_multiple_entities(self) -> None:
        """Test creating multiple entities with incremental indices."""
        context = Context()

        entity1 = context.create_entity()
        entity2 = context.create_entity()
        entity3 = context.create_entity()

        assert entity1._creation_index == 0
        assert entity2._creation_index == 1
        assert entity3._creation_index == 2
        assert context._entity_index == 3
        assert len(context._entities) == 3

    def test_has_entity(self) -> None:
        """Test checking if context has an entity."""
        context = Context()
        entity = context.create_entity()

        assert context.has_entity(entity)

        # Test with entity not in context
        other_entity = Entity()
        assert not context.has_entity(other_entity)

    def test_destroy_entity_success(self) -> None:
        """Test successfully destroying an entity."""
        context = Context()
        entity = context.create_entity()

        # Add some components to entity
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)

        context.destroy_entity(entity)

        assert not entity._is_enabled
        assert len(entity._components) == 0
        assert entity not in context._entities
        assert entity in context._reusable_entities

    def test_destroy_entity_missing(self) -> None:
        """Test destroying an entity not in context raises exception."""
        context = Context()
        entity = Entity()

        with pytest.raises(MissingEntity):
            context.destroy_entity(entity)

    def test_entity_reuse(self) -> None:
        """Test that destroyed entities are reused."""
        context = Context()

        # Create and destroy an entity
        entity1 = context.create_entity()
        entity1_id = id(entity1)
        context.destroy_entity(entity1)

        # Create another entity - should reuse the previous one
        entity2 = context.create_entity()
        entity2_id = id(entity2)

        assert entity1_id == entity2_id  # Same object instance
        assert entity2._is_enabled
        assert entity2._creation_index == 1  # New creation index

    def test_entities_property(self) -> None:
        """Test entities property returns correct set."""
        context = Context()

        entity1 = context.create_entity()
        entity2 = context.create_entity()

        entities = context.entities
        assert len(entities) == 2
        assert entity1 in entities
        assert entity2 in entities

    def test_get_group_new_matcher(self) -> None:
        """Test getting a group with a new matcher."""
        context = Context()
        matcher = Matcher(Position)

        group = context.get_group(matcher)

        assert isinstance(group, Group)
        assert group._matcher == matcher
        assert matcher in context._groups
        assert context._groups[matcher] == group

    def test_get_group_existing_matcher(self) -> None:
        """Test getting a group with an existing matcher returns same instance."""
        context = Context()
        matcher = Matcher(Position)

        group1 = context.get_group(matcher)
        group2 = context.get_group(matcher)

        assert group1 is group2  # Same instance

    def test_get_group_with_existing_entities(self) -> None:
        """Test that group contains existing matching entities."""
        context = Context()

        # Create entities with components
        entity1 = context.create_entity()
        entity1.add(Position, 10, 20)

        entity2 = context.create_entity()
        entity2.add(Velocity, 1, 2)

        entity3 = context.create_entity()
        entity3.add(Position, 30, 40)
        entity3.add(Velocity, 3, 4)

        # Get group for entities with Position
        matcher = Matcher(Position)
        group = context.get_group(matcher)

        assert len(group.entities) == 2
        assert entity1 in group.entities
        assert entity3 in group.entities
        assert entity2 not in group.entities

    def test_group_updates_on_component_add(self) -> None:
        """Test that groups are updated when components are added."""
        context = Context()
        entity = context.create_entity()

        matcher = Matcher(Position)
        group = context.get_group(matcher)

        # Initially empty
        assert len(group.entities) == 0

        # Add matching component
        entity.add(Position, 10, 20)

        # Group should be updated
        assert len(group.entities) == 1
        assert entity in group.entities

    def test_group_updates_on_component_remove(self) -> None:
        """Test that groups are updated when components are removed."""
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)

        matcher = Matcher(Position)
        group = context.get_group(matcher)

        # Initially contains entity
        assert len(group.entities) == 1
        assert entity in group.entities

        # Remove matching component
        entity.remove(Position)

        # Group should be updated
        assert len(group.entities) == 0
        assert entity not in group.entities

    def test_group_updates_on_component_replace(self) -> None:
        """Test that groups are updated when components are replaced."""
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)

        matcher = Matcher(Position)
        group = context.get_group(matcher)

        # Mock group update method to verify it's called
        with patch.object(group, "update_entity") as mock_update:
            # Replace component
            old_pos = entity.get(Position)
            entity.replace(Position, 30, 40)
            new_pos = entity.get(Position)

            # Group update should be called
            mock_update.assert_called_once_with(entity, old_pos, new_pos)

    def test_multiple_groups_same_entity(self) -> None:
        """Test that entity can belong to multiple groups."""
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)

        pos_matcher = Matcher(Position)
        vel_matcher = Matcher(Velocity)
        both_matcher = Matcher(Position, Velocity)

        pos_group = context.get_group(pos_matcher)
        vel_group = context.get_group(vel_matcher)
        both_group = context.get_group(both_matcher)

        assert entity in pos_group.entities
        assert entity in vel_group.entities
        assert entity in both_group.entities

    def test_context_repr(self) -> None:
        """Test context string representation."""
        context = Context()

        # Empty context
        assert "Context (0/0)" in str(context)

        # With entities
        entity1 = context.create_entity()
        entity2 = context.create_entity()
        assert "Context (2/0)" in str(context)

        # With reusable entities
        context.destroy_entity(entity1)
        assert "Context (1/1)" in str(context)

    def test_event_wiring_on_entity_creation(self) -> None:
        """Test that entity events are properly wired to context handlers."""
        context = Context()
        entity = context.create_entity()

        # Mock context handlers
        with (
            patch.object(context, "_comp_added_or_removed") as mock_added_removed,
            patch.object(context, "_comp_replaced") as mock_replaced,
        ):

            # Manually add listeners (simulate what should happen in create_entity)
            entity.on_component_added += context._comp_added_or_removed
            entity.on_component_removed += context._comp_added_or_removed
            entity.on_component_replaced += context._comp_replaced

            # Add component - should trigger handler
            entity.add(Position, 10, 20)
            mock_added_removed.assert_called_once()

            # Replace component - should trigger handler
            entity.replace(Position, 30, 40)
            mock_replaced.assert_called_once()

    def test_complex_scenario(self) -> None:
        """Test a complex scenario with multiple entities and groups."""
        context = Context()

        # Create entities with different component combinations
        player = context.create_entity()
        player.add(Position, 0, 0)
        player.add(Health, 100, 100)
        player.add(Name, "Player")

        enemy1 = context.create_entity()
        enemy1.add(Position, 10, 10)
        enemy1.add(Health, 50, 50)

        enemy2 = context.create_entity()
        enemy2.add(Position, 20, 20)
        enemy2.add(Health, 30, 30)

        projectile = context.create_entity()
        projectile.add(Position, 5, 5)
        projectile.add(Velocity, 10, 0)

        # Create groups
        all_entities_group = context.get_group(
            Matcher(any_of=(Position, Health, Velocity))
        )
        living_entities_group = context.get_group(Matcher(Health))
        moving_entities_group = context.get_group(Matcher(Velocity))
        positioned_entities_group = context.get_group(Matcher(Position))
        named_entities_group = context.get_group(Matcher(Name))

        # Verify group memberships
        assert len(all_entities_group.entities) == 4
        assert len(living_entities_group.entities) == 3  # player, enemy1, enemy2
        assert len(moving_entities_group.entities) == 1  # projectile
        assert len(positioned_entities_group.entities) == 4  # all have position
        assert len(named_entities_group.entities) == 1  # only player

        # Destroy an entity and verify groups update
        context.destroy_entity(enemy1)
        assert len(living_entities_group.entities) == 2
        assert len(positioned_entities_group.entities) == 3

        # Add component to existing entity and verify groups update
        projectile.add(Health, 1, 1)
        assert len(living_entities_group.entities) == 3
        assert projectile in living_entities_group.entities

    def test_matcher_combinations(self) -> None:
        """Test different matcher combinations with groups."""
        context = Context()

        # Create test entity
        entity = context.create_entity()
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)
        entity.add(Health, 100, 100)

        # Test different matcher types
        all_matcher = Matcher(Position, Velocity)  # all_of
        any_matcher = Matcher(any_of=(Position, Age))  # any_of
        none_matcher = Matcher(Position, none_of=(Age,))  # none_of

        all_group = context.get_group(all_matcher)
        any_group = context.get_group(any_matcher)
        none_group = context.get_group(none_matcher)

        assert entity in all_group.entities  # has both Position and Velocity
        assert entity in any_group.entities  # has Position (not Age)
        assert entity in none_group.entities  # has Position and doesn't have Age

        # Add Age component
        entity.add(Age, 25)

        # Groups should update
        assert entity in all_group.entities  # still has Position and Velocity
        assert entity in any_group.entities  # now has both Position and Age
        assert entity not in none_group.entities  # now has Age (excluded)

    def test_entity_lifecycle_in_context(self) -> None:
        """Test complete entity lifecycle within context."""
        context = Context()

        # Create entity
        entity = context.create_entity()
        creation_index = entity._creation_index
        assert context.has_entity(entity)

        # Add components
        entity.add(Position, 10, 20)
        entity.add(Health, 100, 100)

        # Create group to track entity
        group = context.get_group(Matcher(Position))
        assert entity in group.entities

        # Modify entity
        entity.replace(Position, 30, 40)
        assert entity in group.entities  # still in group

        # Remove component
        entity.remove(Health)
        assert entity in group.entities  # still has Position

        # Destroy entity
        context.destroy_entity(entity)
        assert not context.has_entity(entity)
        assert entity not in group.entities
        assert not entity._is_enabled

        # Create new entity (should reuse the old one)
        new_entity = context.create_entity()
        assert new_entity is entity  # Same object
        assert new_entity._creation_index == creation_index + 1  # New index
        assert new_entity._is_enabled
