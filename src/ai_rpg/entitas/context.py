from typing import Dict, List, Optional, Set, Type

from .components import Component
from .entity import Entity
from .exceptions import MissingEntity
from .group import Group
from .matcher import Matcher


class Context:
    """A context owns the component storage for a group of entities.

    This is a sparse-set / structure-of-arrays style ECS context:

    - entities are identified by a dense integer ``index``; each index owns one
      handle object (its identity), and slots are never reused;
    - components are stored in per-type pools (``dict[type, list]``) addressed
      directly by the entity index;
    - groups (queries) track matching entity indices and are kept up to date
      through entity component events.

    The public :class:`Entity` handle, :class:`Group` and :class:`Matcher` APIs
    are intentionally kept stable so callers do not need to know whether
    components live on the entity or in the context.
    """

    def __init__(self) -> None:
        #: Component pools, addressed by entity index. ``None`` means "absent".
        self._pools: Dict[Type[Component], List[Optional[Component]]] = {}

        #: The live handle for each slot; ``None`` means the slot is dead.
        self._handles: List[Optional[Entity]] = []

        #: Dictionary of matchers mapping groups.
        self._groups: Dict[Matcher, Group] = {}

    # ------------------------------------------------------------------ #
    # Entity storage protocol (used by Entity handles)
    # ------------------------------------------------------------------ #
    def store_has(self, index: int, comp_type: Type[Component]) -> bool:
        pool = self._pools.get(comp_type)
        return pool is not None and index < len(pool) and pool[index] is not None

    def store_get(self, index: int, comp_type: Type[Component]) -> Component:
        comp = self._pools[comp_type][index]
        assert comp is not None
        return comp

    def store_add(
        self, index: int, comp_type: Type[Component], comp: Component
    ) -> None:
        pool = self._pools.get(comp_type)
        if pool is None:
            pool = []
            self._pools[comp_type] = pool
        while len(pool) <= index:
            pool.append(None)
        pool[index] = comp

    def store_remove(self, index: int, comp_type: Type[Component]) -> None:
        pool = self._pools.get(comp_type)
        if pool is not None and index < len(pool):
            pool[index] = None

    def store_replace(
        self, index: int, comp_type: Type[Component], comp: Component
    ) -> None:
        self.store_add(index, comp_type, comp)

    def store_component_types(self, index: int) -> List[Type[Component]]:
        return [
            comp_type
            for comp_type, pool in self._pools.items()
            if index < len(pool) and pool[index] is not None
        ]

    def store_components(self, index: int) -> List[Component]:
        result: List[Component] = []
        for pool in self._pools.values():
            if index < len(pool):
                comp = pool[index]
                if comp is not None:
                    result.append(comp)
        return result

    def store_is_valid(self, entity: Entity) -> bool:
        """Whether ``entity`` is the live handle currently held by its slot."""
        index = entity._index
        return 0 <= index < len(self._handles) and self._handles[index] is entity

    def entity_at(self, index: int) -> Entity:
        """Returns the live handle for a slot index."""
        handle = self._handles[index]
        assert handle is not None
        return handle

    # ------------------------------------------------------------------ #
    # Context API
    # ------------------------------------------------------------------ #
    @property
    def entities(self) -> Set[Entity]:
        """Gets the set of all active entities in this context.

        :return: Set of active entities
        """
        result: Set[Entity] = set()
        for handle in self._handles:
            if handle is not None:
                result.add(handle)
        return result

    #: Backwards compatible alias for :attr:`entities`.
    @property
    def _entities(self) -> Set[Entity]:
        return self.entities

    @property
    def entity_count(self) -> int:
        """Gets the number of active entities in this context.

        :return: Number of active entities
        """
        return sum(1 for handle in self._handles if handle is not None)

    def has_entity(self, entity: Entity) -> bool:
        """Checks if the context contains this entity.

        :param entity: Entity to check for
        :return: True if the entity exists in this context, False otherwise
        """
        if not isinstance(entity, Entity) or entity._context is not self:
            return False
        return bool(self.store_is_valid(entity))

    def create_entity(self) -> Entity:
        """Creates an entity by appending a new dense slot.

        Slots are never reused; a destroyed entity's components (and its slot in
        every pool) stay dead. Components are stored in the context pools, never
        on the entity handle.

        :return: A new entity handle
        """
        index = len(self._handles)
        entity = Entity(self, index)
        self._handles.append(entity)

        entity.on_component_added += self._comp_added_or_removed
        entity.on_component_removed += self._comp_added_or_removed
        entity.on_component_replaced += self._comp_replaced

        return entity

    def destroy_entity(self, entity: Entity) -> None:
        """Removes an entity from the context and marks its slot dead.

        If the context does not contain this entity, a MissingEntity
        exception is raised.

        :param entity: Entity to destroy
        :raises MissingEntity: If the entity is not in this context
        """
        if not self.has_entity(entity):
            raise MissingEntity(
                f"Cannot destroy entity {entity}: not found in context."
            )

        entity.remove_all()
        self._handles[entity._index] = None

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

        group = Group(self, matcher)

        for index, handle in enumerate(self._handles):
            if handle is not None:
                group.handle_index_silently(index)

        self._groups[matcher] = group

        return group

    def matches_index(self, index: int, matcher: Matcher) -> bool:
        """Evaluates a matcher against a raw entity index (no handle needed)."""
        all_of = matcher.all_of
        any_of = matcher.any_of
        none_of = matcher.none_of

        if all_of is not None:
            for comp_type in all_of:
                if not self.store_has(index, comp_type):
                    return False

        if any_of is not None:
            if not any(self.store_has(index, comp_type) for comp_type in any_of):
                return False

        if none_of is not None:
            if any(self.store_has(index, comp_type) for comp_type in none_of):
                return False

        return True

    def _comp_added_or_removed(self, entity: Entity, comp: Component) -> None:
        """Handles component addition or removal events.

        Updates all groups to reflect the component change.

        :param entity: Entity that had a component added or removed
        :param comp: Component that was added or removed
        """
        for group in self._groups.values():
            group.handle_index(entity._index, comp)

    def _comp_replaced(
        self, entity: Entity, previous_comp: Component, new_comp: Component
    ) -> None:
        """Handles component replacement events.

        Updates all groups to reflect the component replacement.

        :param entity: Entity that had a component replaced
        :param previous_comp: The component that was replaced
        :param new_comp: The new component
        """
        for group in self._groups.values():
            group.update_index(entity._index, previous_comp, new_comp)

    def __repr__(self) -> str:
        """Returns a string representation of the context.

        Format: <Context (active_entities)>
        """
        return f"<Context ({self.entity_count})>"
