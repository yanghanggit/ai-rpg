"""
Tests for the Group class in the entitas framework.

Groups track matching entity *indices* internally and expose entity handles
through the ``entities`` property.
"""

from unittest.mock import Mock

import pytest

from ai_rpg.entitas import Context, Matcher
from ai_rpg.entitas.exceptions import GroupSingleEntity
from ai_rpg.entitas.group import Group
from ecs_testing import Health, Position, Velocity


class TestGroupBasics:
    def test_group_metadata(self) -> None:
        context = Context()
        matcher = Matcher(Position)
        group = context.get_group(matcher)

        assert group.matcher is matcher
        assert group.entity_count == 0
        assert group.entities == set()
        assert "Group" in repr(group)

    def test_group_tracks_matching_entities(self) -> None:
        context = Context()
        group = context.get_group(Matcher(Position))

        entity = context.create_entity()
        entity.add(Position, 1, 2)

        assert group.entity_count == 1
        assert entity in group.entities

    def test_group_updates_on_add_and_remove(self) -> None:
        context = Context()
        entity = context.create_entity()
        group = context.get_group(Matcher(Position, Velocity))

        entity.add(Position, 1, 2)
        assert group.entity_count == 0  # still missing Velocity

        entity.add(Velocity, 3, 4)
        assert group.entity_count == 1

        entity.remove(Velocity)
        assert group.entity_count == 0


class TestGroupSingleEntity:
    def test_empty_returns_none(self) -> None:
        context = Context()
        group = context.get_group(Matcher(Position))
        assert group.single_entity is None

    def test_single_returns_entity(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 1, 2)
        group = context.get_group(Matcher(Position))

        assert group.single_entity == entity

    def test_multiple_raises(self) -> None:
        context = Context()
        first = context.create_entity()
        first.add(Position, 1, 2)
        second = context.create_entity()
        second.add(Position, 3, 4)

        group = context.get_group(Matcher(Position))

        with pytest.raises(GroupSingleEntity):
            _ = group.single_entity


class TestGroupEvents:
    def test_added_event(self) -> None:
        context = Context()
        group = context.get_group(Matcher(Position))
        callback = Mock()
        group.on_entity_added += callback

        entity = context.create_entity()
        entity.add(Position, 1, 2)

        callback.assert_called_once()
        assert callback.call_args.args[0] == entity

    def test_removed_event(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 1, 2)
        group = context.get_group(Matcher(Position))

        callback = Mock()
        group.on_entity_removed += callback

        entity.remove(Position)

        callback.assert_called_once()

    def test_updated_event_on_replace(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 1, 2)
        group = context.get_group(Matcher(Position))

        removed = Mock()
        added = Mock()
        updated = Mock()
        group.on_entity_removed += removed
        group.on_entity_added += added
        group.on_entity_updated += updated

        entity.replace(Position, 3, 4)

        removed.assert_called_once()
        added.assert_called_once()
        updated.assert_called_once()

    def test_no_event_when_adding_unrelated_component(self) -> None:
        context = Context()
        entity = context.create_entity()
        group = context.get_group(Matcher(Position))

        callback = Mock()
        group.on_entity_added += callback

        entity.add(Health, 1, 2)

        callback.assert_not_called()
        assert group.entity_count == 0

    def test_group_is_cached_by_context(self) -> None:
        context = Context()
        assert isinstance(context.get_group(Matcher(Position)), Group)
        assert context.get_group(Matcher(Position)) is context.get_group(
            Matcher(Position)
        )
