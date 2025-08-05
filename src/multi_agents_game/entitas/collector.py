from .group import GroupEvent
from .entity import Entity
from .group import Group
from typing import Dict
from .components import Component


class Collector(object):

    def __init__(self) -> None:
        self._collected_entities: set[Entity] = set()
        self._groups: Dict[Group, GroupEvent] = {}

    @property
    def collected_entities(self) -> set[Entity]:
        return self._collected_entities

    def add(self, group: Group, group_event: GroupEvent) -> None:
        self._groups[group] = group_event

    def activate(self) -> None:
        for group in self._groups:
            group_event = self._groups[group]

            added_event = group_event == GroupEvent.ADDED
            removed_event = group_event == GroupEvent.REMOVED
            added_or_removed_event = group_event == GroupEvent.ADDED_OR_REMOVED

            if added_event or added_or_removed_event:
                group.on_entity_added -= self._add_entity
                group.on_entity_added += self._add_entity

            if removed_event or added_or_removed_event:
                group.on_entity_removed -= self._add_entity
                group.on_entity_removed += self._add_entity

    def deactivate(self) -> None:
        for group in self._groups:
            group.on_entity_added -= self._add_entity
            group.on_entity_removed -= self._add_entity

        self.clear_collected_entities()

    def clear_collected_entities(self) -> None:
        self._collected_entities.clear()

    def _add_entity(self, entity: Entity, component: Component) -> None:
        self._collected_entities.add(entity)

    def __repr__(self) -> str:
        return "<Collector [{}]".format(", ".join(map(str, self._groups)))
