"""
Tests for the Context class in the entitas framework.

The context is now an index based sparse-set/SoA store: it owns the component
pools and recycles entity slots (bumping a version to invalidate stale handles).
"""

from unittest.mock import patch

import pytest

from ai_rpg.entitas import Context, Group, Matcher
from ai_rpg.entitas.exceptions import MissingEntity
from ecs_testing import Age, Health, Name, Position, Velocity


class TestContextLifecycle:
    def test_context_initialization(self) -> None:
        context = Context()

        assert context.entity_count == 0
        assert context._pools == {}
        assert context._groups == {}
        assert context.entities == set()

    def test_create_entity_allocates_dense_slots(self) -> None:
        context = Context()

        entity = context.create_entity()

        assert entity.is_enabled
        assert entity.index == 0
        assert context.entity_count == 1
        assert context.has_entity(entity)

    def test_create_multiple_entities_incremental_indices(self) -> None:
        context = Context()

        e1 = context.create_entity()
        e2 = context.create_entity()
        e3 = context.create_entity()

        assert (e1.index, e2.index, e3.index) == (0, 1, 2)
        assert context.entity_count == 3

    def test_has_entity_rejects_unknown_and_foreign(self) -> None:
        context = Context()
        entity = context.create_entity()

        assert context.has_entity(entity)
        assert not context.has_entity(Context().create_entity())

    def test_destroy_entity_frees_slot(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)

        context.destroy_entity(entity)

        assert not entity.is_enabled
        assert entity.component_count == 0
        assert not context.has_entity(entity)
        assert context.entity_count == 0
        assert not context.store_has(entity.index, Position)

    def test_destroy_missing_entity_raises(self) -> None:
        context = Context()

        with pytest.raises(MissingEntity):
            context.destroy_entity(Context().create_entity())

    def test_destroyed_slot_is_not_reused(self) -> None:
        context = Context()

        entity1 = context.create_entity()
        context.destroy_entity(entity1)

        entity2 = context.create_entity()

        assert entity1.index == 0
        assert entity2.index == 1  # slots are never recycled
        assert entity2.is_enabled
        assert entity2 is not entity1

    def test_components_are_isolated_per_entity(self) -> None:
        context = Context()
        e1 = context.create_entity()
        e2 = context.create_entity()

        e1.add(Position, 1, 1)
        e2.add(Position, 2, 2)

        assert e1.get(Position).x == 1
        assert e2.get(Position).x == 2
        assert e1 != e2

    def test_entities_property_returns_live_handles(self) -> None:
        context = Context()
        entity1 = context.create_entity()
        entity2 = context.create_entity()

        entities = context.entities
        assert len(entities) == 2
        assert entity1 in entities
        assert entity2 in entities

    def test_context_repr(self) -> None:
        context = Context()
        assert "Context (0)" in str(context)

        entity1 = context.create_entity()
        context.create_entity()
        assert "Context (2)" in str(context)

        context.destroy_entity(entity1)
        assert "Context (1)" in str(context)


class TestContextGroups:
    def test_get_group_returns_cached_group(self) -> None:
        context = Context()
        matcher = Matcher(Position)

        group = context.get_group(matcher)

        assert isinstance(group, Group)
        assert group.matcher == matcher
        assert matcher in context._groups
        assert context._groups[matcher] is group
        assert context.get_group(matcher) is group

    def test_group_populated_from_existing_entities(self) -> None:
        context = Context()

        entity1 = context.create_entity()
        entity1.add(Position, 10, 20)

        entity2 = context.create_entity()
        entity2.add(Velocity, 1, 2)

        entity3 = context.create_entity()
        entity3.add(Position, 30, 40)
        entity3.add(Velocity, 3, 4)

        group = context.get_group(Matcher(Position))

        assert group.entity_count == 2
        assert entity1 in group.entities
        assert entity3 in group.entities
        assert entity2 not in group.entities

    def test_group_updates_on_component_add(self) -> None:
        context = Context()
        entity = context.create_entity()
        group = context.get_group(Matcher(Position))

        assert group.entity_count == 0

        entity.add(Position, 10, 20)

        assert group.entity_count == 1
        assert entity in group.entities

    def test_group_updates_on_component_remove(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)
        group = context.get_group(Matcher(Position))

        assert entity in group.entities

        entity.remove(Position)

        assert group.entity_count == 0
        assert entity not in group.entities

    def test_group_updates_on_component_replace(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)
        group = context.get_group(Matcher(Position))

        with patch.object(group, "update_index") as mock_update:
            old_pos = entity.get(Position)
            entity.replace(Position, 30, 40)
            new_pos = entity.get(Position)

            mock_update.assert_called_once_with(entity.index, old_pos, new_pos)

        assert entity in group.entities

    def test_group_removes_destroyed_entity(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)
        group = context.get_group(Matcher(Position))

        assert entity in group.entities

        context.destroy_entity(entity)

        assert group.entity_count == 0
        assert entity not in group.entities

    def test_multiple_groups_same_entity(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)

        pos_group = context.get_group(Matcher(Position))
        vel_group = context.get_group(Matcher(Velocity))
        both_group = context.get_group(Matcher(Position, Velocity))

        assert entity in pos_group.entities
        assert entity in vel_group.entities
        assert entity in both_group.entities

    def test_matcher_combinations(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 10, 20)
        entity.add(Velocity, 1, 2)
        entity.add(Health, 100, 100)

        all_matcher = Matcher(Position, Velocity)
        any_matcher = Matcher(any_of=(Position, Age))
        none_matcher = Matcher(Position, none_of=(Age,))

        all_group = context.get_group(all_matcher)
        any_group = context.get_group(any_matcher)
        none_group = context.get_group(none_matcher)

        assert entity in all_group.entities
        assert entity in any_group.entities
        assert entity in none_group.entities

        entity.add(Age, 25)

        assert entity in all_group.entities
        assert entity in any_group.entities
        assert entity not in none_group.entities

    def test_complex_scenario(self) -> None:
        context = Context()

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

        all_group = context.get_group(Matcher(any_of=(Position, Health, Velocity)))
        living_group = context.get_group(Matcher(Health))
        moving_group = context.get_group(Matcher(Velocity))
        positioned_group = context.get_group(Matcher(Position))
        named_group = context.get_group(Matcher(Name))

        assert all_group.entity_count == 4
        assert living_group.entity_count == 3
        assert moving_group.entity_count == 1
        assert positioned_group.entity_count == 4
        assert named_group.entity_count == 1

        context.destroy_entity(enemy1)
        assert living_group.entity_count == 2
        assert positioned_group.entity_count == 3

        projectile.add(Health, 1, 1)
        assert living_group.entity_count == 3
        assert projectile in living_group.entities


class TestContextEventWiring:
    def test_events_are_wired_on_creation(self) -> None:
        context = Context()
        entity = context.create_entity()

        with (
            patch.object(context, "_comp_added_or_removed") as mock_added_removed,
            patch.object(context, "_comp_replaced") as mock_replaced,
        ):
            entity.on_component_added += context._comp_added_or_removed
            entity.on_component_removed += context._comp_added_or_removed
            entity.on_component_replaced += context._comp_replaced

            entity.add(Position, 10, 20)
            mock_added_removed.assert_called_once()

            entity.replace(Position, 30, 40)
            mock_replaced.assert_called_once()
