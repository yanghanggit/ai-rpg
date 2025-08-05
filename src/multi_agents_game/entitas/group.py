from enum import Enum
from .utils import Event
from .exceptions import GroupSingleEntity
from .matcher import Matcher
from .entity import Entity
from .components import Component
from typing import Optional


class GroupEvent(Enum):
    ADDED = 1
    REMOVED = 2
    ADDED_OR_REMOVED = 3


class Group(object):
    """Represents a group of entities that match a specified matcher.

    Use context.get_group(matcher) to get a group of entities which
    match the specified matcher. Calling context.get_group(matcher) with
    the same matcher will always return the same instance of the group.

    The created group is managed by the context and will always be up to
    date. It will automatically add entities that match the matcher or
    remove entities as soon as they don't match the matcher anymore.
    """

    def __init__(self, matcher: Matcher) -> None:
        """Initializes a new instance of the Group class.

        Args:
            matcher (Matcher): The matcher used to determine if an entity
                belongs to this group.
        """
        #: Occurs when an entity gets added.
        self.on_entity_added = Event()

        #: Occurs when an entity gets removed.
        self.on_entity_removed = Event()

        #: Occurs when a component of an entity in the group gets replaced.
        self.on_entity_updated = Event()

        self._matcher = matcher
        self._entities: set[Entity] = set()

    @property
    def entities(self) -> set[Entity]:
        """Gets the set of entities in this group.

        Returns:
            set[Entity]: The set of entities in this group.
        """
        return self._entities

    @property
    def single_entity(self) -> Optional[Entity]:
        """Returns the only entity in this group.

        Returns:
            Entity: The only entity in this group.

        Raises:
            GroupSingleEntity: If the group has more than one entity.
        """
        count = len(self._entities)

        if count == 1:
            # return min(self._entities)
            return next(iter(self._entities))
        if count == 0:
            return None

        raise GroupSingleEntity(
            "Cannot get a single entity from a group containing {} entities.",
            len(self._entities),
        )

    def handle_entity_silently(self, entity: Entity) -> None:
        """This is used by the context to manage the group.

        Args:
            entity (Entity): The entity to handle.
        """
        if self._matcher.matches(entity):
            self._add_entity_silently(entity)
        else:
            self._remove_entity_silently(entity)

    def handle_entity(self, entity: Entity, component: Component) -> None:
        """This is used by the context to manage the group.

        Args:
            entity (Entity): The entity to handle.
            component (Component): The component of the entity.
        """
        if self._matcher.matches(entity):
            self._add_entity(entity, component)
        else:
            self._remove_entity(entity, component)

    def update_entity(self, entity: Entity, previous_comp: Component, new_comp: Component) -> None:
        """This is used by the context to manage the group.

        Args:
            entity (Entity): The entity to update.
            previous_comp (Component): The previous component of the entity.
            new_comp (Component): The new component of the entity.
        """
        if entity in self._entities:
            self.on_entity_removed(entity, previous_comp)
            self.on_entity_added(entity, new_comp)
            self.on_entity_updated(entity, previous_comp, new_comp)

    def _add_entity_silently(self, entity: Entity) -> bool:
        """Adds an entity to the group without triggering events.

        Args:
            entity (Entity): The entity to add.

        Returns:
            bool: True if the entity was added, False if it was already in the group.
        """
        if entity not in self._entities:
            self._entities.add(entity)
            return True
        return False

    def _add_entity(self, entity: Entity, component: Component) -> None:
        """Adds an entity to the group and triggers the on_entity_added event.

        Args:
            entity (Entity): The entity to add.
            component (Component): The component of the entity.
        """
        entity_added = self._add_entity_silently(entity)
        if entity_added:
            self.on_entity_added(entity, component)

    def _remove_entity_silently(self, entity: Entity) -> bool:
        """Removes an entity from the group without triggering events.

        Args:
            entity (Entity): The entity to remove.

        Returns:
            bool: True if the entity was removed, False if it was not in the group.
        """
        if entity in self._entities:
            self._entities.remove(entity)
            return True
        return False

    def _remove_entity(self, entity: Entity, component: Component) -> None:
        """Removes an entity from the group and triggers the on_entity_removed event.

        Args:
            entity (Entity): The entity to remove.
            component (Component): The component of the entity.
        """
        entity_removed = self._remove_entity_silently(entity)
        if entity_removed:
            self.on_entity_removed(entity, component)

    def __repr__(self) -> str:
        """Returns a string representation of the Group.

        Returns:
            str: A string representation of the Group.
        """
        return "<Group [{}]>".format(self._matcher)
