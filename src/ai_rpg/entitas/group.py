from enum import Enum
from typing import Optional, Set

from .components import Component
from .context_protocol import ContextProtocol
from .entity import Entity
from .event import Event
from .exceptions import GroupSingleEntity
from .matcher import Matcher


class GroupEvent(Enum):
    """Enumeration of group events for entity tracking."""

    ADDED = 1
    REMOVED = 2
    ADDED_OR_REMOVED = 3


class Group:
    """Represents a group of entities that match a specified matcher.

    Use context.get_group(matcher) to get a group of entities which
    match the specified matcher. Calling context.get_group(matcher) with
    the same matcher will always return the same instance of the group.

    Internally the group stores entity *indices* rather than entity objects;
    :attr:`entities` materializes handles on demand through the owning context.
    """

    def __init__(self, context: ContextProtocol, matcher: Matcher) -> None:
        """Initializes a new instance of the Group class.

        :param context: The owning query store (used to evaluate matches)
        :param matcher: The matcher used to determine if an entity belongs to this group
        """
        #: Occurs when an entity gets added.
        self.on_entity_added: Event = Event()

        #: Occurs when an entity gets removed.
        self.on_entity_removed: Event = Event()

        #: Occurs when a component of an entity in the group gets replaced.
        self.on_entity_updated: Event = Event()

        self._context: ContextProtocol = context
        self._matcher: Matcher = matcher
        self._indices: Set[int] = set()

    @property
    def entities(self) -> Set[Entity]:
        """Gets the set of entities in this group.

        The set is rebuilt on each access from the tracked indices.

        :return: Set of entities in this group
        """
        context = self._context
        return {context.entity_at(index) for index in self._indices}

    @property
    def entity_count(self) -> int:
        """Gets the number of entities in this group.

        :return: Number of entities in this group
        """
        return len(self._indices)

    @property
    def matcher(self) -> Matcher:
        """Gets the matcher used by this group.

        :return: The matcher that defines this group's criteria
        """
        return self._matcher

    @property
    def single_entity(self) -> Optional[Entity]:
        """Returns the only entity in this group.

        :return: The single entity if group contains exactly one entity, None if empty
        :raises GroupSingleEntity: If the group has more than one entity
        """
        count = len(self._indices)

        if count == 1:
            return self._context.entity_at(next(iter(self._indices)))
        if count == 0:
            return None

        raise GroupSingleEntity(
            f"Cannot get a single entity from a group containing {count} entities.", ""
        )

    # ------------------------------------------------------------------ #
    # Index based internals (used by the context)
    # ------------------------------------------------------------------ #
    def handle_index_silently(self, index: int) -> None:
        """Adds/removes an index without triggering events."""
        if self._context.matches_index(index, self._matcher):
            self._add_index_silently(index)
        else:
            self._remove_index_silently(index)

    def handle_index(self, index: int, component: Component) -> None:
        """Adds/removes an index and triggers the appropriate events."""
        if self._context.matches_index(index, self._matcher):
            self._add_index(index, component)
        else:
            self._remove_index(index, component)

    def update_index(
        self, index: int, previous_comp: Component, new_comp: Component
    ) -> None:
        """Notifies the group that a component of one of its members changed."""
        if index in self._indices:
            entity = self._context.entity_at(index)
            self.on_entity_removed(entity, previous_comp)
            self.on_entity_added(entity, new_comp)
            self.on_entity_updated(entity, previous_comp, new_comp)

    def _add_index_silently(self, index: int) -> bool:
        if index not in self._indices:
            self._indices.add(index)
            return True
        return False

    def _add_index(self, index: int, component: Component) -> None:
        if self._add_index_silently(index):
            self.on_entity_added(self._context.entity_at(index), component)

    def _remove_index_silently(self, index: int) -> bool:
        if index in self._indices:
            self._indices.remove(index)
            return True
        return False

    def _remove_index(self, index: int, component: Component) -> None:
        if self._remove_index_silently(index):
            self.on_entity_removed(self._context.entity_at(index), component)

    def __repr__(self) -> str:
        """Returns a string representation of the Group.

        :return: String representation showing the matcher and entity count
        """
        return f"<Group [{self._matcher}] ({len(self._indices)} entities)>"
