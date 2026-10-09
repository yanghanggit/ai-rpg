"""The structural interface that ``Context`` exposes to internal collaborators.

``Context`` is the concrete ECS storage, but ``Entity`` and ``Group`` cannot
import it for typing: ``context.py`` already imports both of them at runtime, so
a reverse import would form an import cycle. Instead they depend on this single
:class:`typing.Protocol`, which ``Context`` satisfies structurally.

``Entity`` and ``Matcher`` are imported only under ``TYPE_CHECKING`` (all
annotations are strings via ``from __future__ import annotations``), so this
module has no runtime dependency on the rest of the package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from .components import Component

if TYPE_CHECKING:
    from .entity import Entity
    from .matcher import Matcher


class ContextProtocol(Protocol):
    """The slice of :class:`~ai_rpg.entitas.context.Context` used internally.

    It bundles what an :class:`~ai_rpg.entitas.entity.Entity` needs to read and
    write its components, and what a :class:`~ai_rpg.entitas.group.Group` needs
    to resolve and match entities.
    """

    # --- component storage (used by Entity) ---
    def store_has(self, index: int, comp_type: type[Component]) -> bool:
        """Whether the entity at ``index`` has ``comp_type``."""
        ...

    def store_get(self, index: int, comp_type: type[Component]) -> Component:
        """Returns the component of type ``comp_type`` at ``index``."""
        ...

    def store_add(
        self, index: int, comp_type: type[Component], comp: Component
    ) -> None:
        """Stores ``comp`` under ``comp_type`` at ``index``."""
        ...

    def store_remove(self, index: int, comp_type: type[Component]) -> None:
        """Removes the component of type ``comp_type`` at ``index``."""
        ...

    def store_replace(
        self, index: int, comp_type: type[Component], comp: Component
    ) -> None:
        """Replaces the component of type ``comp_type`` at ``index``."""
        ...

    def store_component_types(self, index: int) -> list[type[Component]]:
        """Returns the component types attached to the entity at ``index``."""
        ...

    def store_components(self, index: int) -> list[Component]:
        """Returns the component instances attached to the entity at ``index``."""
        ...

    def store_is_valid(self, entity: Entity) -> bool:
        """Whether ``entity`` is the live handle currently held by its slot."""
        ...

    # --- query resolution (used by Group) ---
    def entity_at(self, index: int) -> Entity:
        """Returns the live entity handle for a dense slot index."""
        ...

    def matches_index(self, index: int, matcher: Matcher) -> bool:
        """Returns whether the entity at ``index`` satisfies ``matcher``."""
        ...
