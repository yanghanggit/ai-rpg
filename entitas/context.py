from collections import deque

from .entity import Entity
from .matcher import Matcher
from .group import Group
from .exceptions import MissingEntity
from typing import Any, Dict
from .entity_index import AbstractEntityIndex


class Context(object):
    """A context is a data structure managing entities."""

    def __init__(self) -> None:

        #: Entities retained by this context.
        self._entities: set[Entity] = set()

        #: An object pool to recycle entities.
        self._reusable_entities: deque[Entity] = deque()

        #: Entities counter.
        self._entity_index: int = 0

        #: Dictionary of matchers mapping groups.
        self._groups: Dict[Matcher, Group] = {}

        self._entity_indices: Dict[Any, AbstractEntityIndex] = {}

    @property
    def entities(self) -> set[Entity]:
        return self._entities

    def has_entity(self, entity: Entity) -> bool:
        """Checks if the context contains this entity.
        :param entity: Entity
        :rtype: bool
        """
        return entity in self._entities

    def create_entity(self) -> Entity:
        """Creates an entity. Pop one entity from the pool if it is not
        empty, otherwise creates a new one. Increments the entity index.
        Then adds the entity to the list.
        :rtype: Entity
        """
        entity = self._reusable_entities.pop() if self._reusable_entities else Entity()

        entity.activate(self._entity_index)
        self._entity_index += 1

        self._entities.add(entity)

        entity.on_component_added += self._comp_added_or_removed
        entity.on_component_removed += self._comp_added_or_removed
        entity.on_component_replaced += self._comp_replaced

        return entity

    def destroy_entity(self, entity: Entity) -> None:
        """Removes an entity from the list and add it to the pool. If
        the context does not contain this entity, a
        :class:`MissingEntity` exception is raised.
        :param entity: Entity
        """
        if not self.has_entity(entity):
            raise MissingEntity()

        entity.destroy()

        self._entities.remove(entity)
        self._reusable_entities.append(entity)

    def get_group(self, matcher: Matcher) -> Group:
        """User can ask for a group of entities from the context. The
        group is identified through a :class:`Matcher`.
        :param entity: Matcher
        """
        if matcher in self._groups:
            return self._groups[matcher]

        group = Group(matcher)

        for entity in self._entities:
            group.handle_entity_silently(entity)

        self._groups[matcher] = group

        return group

    def set_unique_component(self, comp_type: Any, *args: Any) -> None:
        self.create_entity().add(comp_type, *args)

    def get_unique_component(self, comp_type: Any) -> Any:
        group = self.get_group(Matcher(comp_type))
        if group.single_entity is not None:
            return group.single_entity.get(comp_type)
        return None

    def add_entity_index(self, entity_index: AbstractEntityIndex) -> None:
        self._entity_indices[entity_index.type] = entity_index

    def get_entity_index(self, comp_type: Any) -> AbstractEntityIndex:
        return self._entity_indices[comp_type]

    def _comp_added_or_removed(self, entity: Entity, comp: Any) -> None:
        for matcher in self._groups:
            self._groups[matcher].handle_entity(entity, comp)

    def _comp_replaced(self, entity: Entity, previous_comp: Any, new_comp: Any) -> None:
        for matcher in self._groups:
            group = self._groups[matcher]
            group.update_entity(entity, previous_comp, new_comp)

    def __repr__(self) -> str:
        return "<Context ({}/{})>".format(
            len(self._entities), len(self._reusable_entities)
        )
