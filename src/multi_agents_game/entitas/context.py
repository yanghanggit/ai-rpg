from collections import deque
from typing import Dict, Set

from .components import Component
from .entity import Entity
from .exceptions import MissingEntity
from .group import Group
from .matcher import Matcher


class Context(object):
    """A context is a data structure managing entities.

    The context manages the lifecycle of entities and provides
    functionality for creating, destroying, and organizing entities
    into groups based on component patterns.
    """

    def __init__(self) -> None:

        #: Entities retained by this context.
        self._entities: Set[Entity] = set()

        #: An object pool to recycle entities.
        self._reusable_entities: deque[Entity] = deque()

        #: Entities counter.
        self._entity_index: int = 0

        #: Dictionary of matchers mapping groups.
        self._groups: Dict[Matcher, Group] = {}

    @property
    def entities(self) -> Set[Entity]:
        """Gets the set of all active entities in this context.

        :return: Set of active entities
        """
        return self._entities

    @property
    def entity_count(self) -> int:
        """Gets the number of active entities in this context.

        :return: Number of active entities
        """
        return len(self._entities)

    @property
    def reusable_entity_count(self) -> int:
        """Gets the number of entities available for reuse.

        :return: Number of reusable entities in the pool
        """
        return len(self._reusable_entities)

    def has_entity(self, entity: Entity) -> bool:
        """Checks if the context contains this entity.

        :param entity: Entity to check for
        :return: True if the entity exists in this context, False otherwise
        """
        return entity in self._entities

    def create_entity(self) -> Entity:
        """Creates an entity.

        Pop one entity from the pool if it is not empty, otherwise
        creates a new one. Increments the entity index and adds the
        entity to the active entities set.

        :return: A new or recycled entity
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
        """Removes an entity from the active set and adds it to the pool.

        If the context does not contain this entity, a MissingEntity
        exception is raised.

        :param entity: Entity to destroy
        :raises MissingEntity: If the entity is not in this context
        """
        if not self.has_entity(entity):
            raise MissingEntity(
                f"Cannot destroy entity {entity}: not found in context."
            )

        entity.destroy()

        self._entities.remove(entity)
        self._reusable_entities.append(entity)

    def get_group(self, matcher: Matcher) -> Group:
        """Gets a group of entities from the context.

        The group is identified through a Matcher. If the group doesn't
        exist yet, it will be created and populated with all matching
        entities from the context.

        :param matcher: Matcher defining the group criteria
        :return: Group containing entities matching the criteria
        """
        if matcher in self._groups:
            return self._groups[matcher]

        group = Group(matcher)

        for entity in self._entities:
            group.handle_entity_silently(entity)

        self._groups[matcher] = group

        return group

    def _comp_added_or_removed(self, entity: Entity, comp: Component) -> None:
        """Handles component addition or removal events.

        Updates all groups to reflect the component change.

        :param entity: Entity that had a component added or removed
        :param comp: Component that was added or removed
        """
        for matcher in self._groups:
            self._groups[matcher].handle_entity(entity, comp)

    def _comp_replaced(
        self, entity: Entity, previous_comp: Component, new_comp: Component
    ) -> None:
        """Handles component replacement events.

        Updates all groups to reflect the component replacement.

        :param entity: Entity that had a component replaced
        :param previous_comp: The component that was replaced
        :param new_comp: The new component
        """
        for matcher in self._groups:
            group = self._groups[matcher]
            group.update_entity(entity, previous_comp, new_comp)

    def __repr__(self) -> str:
        """Returns a string representation of the context.

        Format: <Context (active_entities/reusable_entities)>
        """
        return f"<Context ({len(self._entities)}/{len(self._reusable_entities)})>"
