from .group import GroupEvent
from .entity import Entity
from .group import Group
from typing import Dict, Set
from .components import Component


class Collector(object):
    """A collector observes groups and collects entities based on group events.

    The collector monitors one or more groups for entity additions, removals,
    or both, and maintains a collection of entities that have triggered
    the specified events. This is useful for systems that need to process
    entities that have changed in specific ways.
    """

    def __init__(self) -> None:
        self._collected_entities: Set[Entity] = set()
        self._groups: Dict[Group, GroupEvent] = {}

    @property
    def collected_entities(self) -> Set[Entity]:
        """Gets the set of collected entities.

        :return: Set of entities that have triggered the monitored events
        """
        return self._collected_entities

    @property
    def collected_entity_count(self) -> int:
        """Gets the number of collected entities.

        :return: Number of entities in the collection
        """
        return len(self._collected_entities)

    def add(self, group: Group, group_event: GroupEvent) -> None:
        """Adds a group to monitor for the specified event type.

        :param group: Group to monitor for events
        :param group_event: Type of event to collect (ADDED, REMOVED, or ADDED_OR_REMOVED)
        """
        self._groups[group] = group_event

    def activate(self) -> None:
        """Activates the collector by subscribing to group events.

        This method sets up event listeners for all registered groups
        based on their configured event types.
        """
        for group, group_event in self._groups.items():
            # Subscribe to entity added events if needed
            if group_event in (GroupEvent.ADDED, GroupEvent.ADDED_OR_REMOVED):
                group.on_entity_added -= self._add_entity
                group.on_entity_added += self._add_entity

            # Subscribe to entity removed events if needed
            if group_event in (GroupEvent.REMOVED, GroupEvent.ADDED_OR_REMOVED):
                group.on_entity_removed -= self._add_entity
                group.on_entity_removed += self._add_entity

    def deactivate(self) -> None:
        """Deactivates the collector by unsubscribing from all group events.

        This method removes all event listeners and clears the collected entities.
        """
        for group in self._groups:
            group.on_entity_added -= self._add_entity
            group.on_entity_removed -= self._add_entity

        self.clear_collected_entities()

    def clear_collected_entities(self) -> None:
        """Clears all collected entities from the collection."""
        self._collected_entities.clear()

    def _add_entity(self, entity: Entity, component: Component) -> None:
        """Internal method to add an entity to the collection.

        :param entity: Entity to add to the collection
        :param component: Component involved in the event (not used but required by event signature)
        """
        self._collected_entities.add(entity)

    def __repr__(self) -> str:
        """Returns a string representation of the collector.

        Format: <Collector [Group1, Group2, ...]>
        """
        group_strs = [str(group) for group in self._groups.keys()]
        return f"<Collector [{', '.join(group_strs)}]>"
