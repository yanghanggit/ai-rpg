"""
Tests for the Collector class in the entitas framework.
"""

from ai_rpg.entitas import Collector, Context, GroupEvent, Matcher
from ecs_testing import Position, Velocity


class TestCollector:
    def test_collect_added_entities(self) -> None:
        context = Context()
        group = context.get_group(Matcher(Position))
        collector = Collector()
        collector.add(group, GroupEvent.ADDED)
        collector.activate()

        entity = context.create_entity()
        entity.add(Position, 1, 2)

        assert collector.collected_entity_count == 1
        assert entity in collector.collected_entities

    def test_collect_removed_entities(self) -> None:
        context = Context()
        entity = context.create_entity()
        entity.add(Position, 1, 2)
        group = context.get_group(Matcher(Position))

        collector = Collector()
        collector.add(group, GroupEvent.REMOVED)
        collector.activate()

        entity.remove(Position)

        assert entity in collector.collected_entities

    def test_collect_added_or_removed(self) -> None:
        context = Context()
        group = context.get_group(Matcher(Position))
        collector = Collector()
        collector.add(group, GroupEvent.ADDED_OR_REMOVED)
        collector.activate()

        entity = context.create_entity()
        entity.add(Position, 1, 2)
        assert entity in collector.collected_entities

        collector.clear_collected_entities()
        entity.remove(Position)
        assert entity in collector.collected_entities

    def test_collect_ignores_unrelated_events(self) -> None:
        context = Context()
        group = context.get_group(Matcher(Position))
        collector = Collector()
        collector.add(group, GroupEvent.ADDED)
        collector.activate()

        entity = context.create_entity()
        entity.add(Velocity, 1, 2)

        assert collector.collected_entity_count == 0

    def test_clear_and_deactivate(self) -> None:
        context = Context()
        group = context.get_group(Matcher(Position))
        collector = Collector()
        collector.add(group, GroupEvent.ADDED)
        collector.activate()

        entity = context.create_entity()
        entity.add(Position, 1, 2)
        assert collector.collected_entity_count == 1

        collector.clear_collected_entities()
        assert collector.collected_entity_count == 0

        collector.deactivate()

        other = context.create_entity()
        other.add(Position, 3, 4)
        assert collector.collected_entity_count == 0
