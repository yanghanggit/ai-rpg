"""
An entity is a lightweight *handle* that identifies a single row inside the
component storage owned by its :class:`~ai_rpg.entitas.context.Context`.

The entity itself never owns component data. It only keeps:

- ``_context``: the :class:`Context` that stores its components,
- ``_index``: the dense slot index inside that context,
- ``_name`` : optional human readable name (managed by the game layer).

Handle identity is object identity: a live entity is represented by exactly one
handle object, and destroying it clears the context's reference to that object.

Components are Pydantic ``BaseModel`` classes for validation and serialization.
"""

from __future__ import annotations

from typing import Any, List, Tuple, Type, TypeVar, cast

from .components import Component
from .context_protocol import ContextProtocol
from .event import Event
from .exceptions import AlreadyAddedComponent, EntityNotEnabled, MissingComponent

# 用于泛型组件类型的类型变量，绑定到Component基类
ComponentT = TypeVar("ComponentT", bound=Component)


class Entity:
    """A lightweight handle to a row of components owned by a context.

    Entities are always created through ``context.create_entity()`` and
    destroyed with ``context.destroy_entity(entity)``. The handle carries no
    component data itself: components live in the owning context's pools and
    are addressed by the handle's dense ``index``.

    You can add, replace and remove components through this handle; the data is
    always stored by the underlying context, never on the handle.
    """

    __slots__ = (
        "_context",
        "_index",
        "_name",
        "on_component_added",
        "on_component_removed",
        "on_component_replaced",
    )

    def __init__(self, context: ContextProtocol, index: int) -> None:
        #: The context that owns this entity's component storage.
        self._context: ContextProtocol = context

        #: Dense slot index inside the context.
        self._index: int = index

        #: Optional human readable name (managed by RPGEntityManager).
        self._name: str = ""

        #: Occurs when a component gets added.
        self.on_component_added: Event = Event()

        #: Occurs when a component gets removed.
        self.on_component_removed: Event = Event()

        #: Occurs when a component gets replaced.
        self.on_component_replaced: Event = Event()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def _ensure_enabled(self, operation: str, comp_type: Type[Component]) -> None:
        """Ensures the entity is still live before performing operations.

        An entity is live while its context still holds this exact handle object
        for the slot; destroying the entity clears that reference.

        :param operation: The operation being performed (for error messages)
        :param comp_type: The component type involved
        :raises EntityNotEnabled: If the entity is not enabled
        """
        if not self._context.store_is_valid(self):
            raise EntityNotEnabled(
                f"Cannot {operation} component '{comp_type.__name__}': {self} is not enabled."
            )

    def _create_component(self, comp_type: Type[Component], *args: Any) -> Component:
        """Creates a component instance using Pydantic BaseModel.

        :param comp_type: Component type (Pydantic BaseModel subclass)
        :param *args: Component field values
        :return: Component instance
        """
        # Get field names from Pydantic BaseModel
        field_names = list(comp_type.model_fields.keys())

        # Handle components with no fields (like Marker)
        if len(field_names) == 0:
            if len(args) != 0:
                raise ValueError(
                    f"Component {comp_type.__name__} expects no arguments, got {len(args)}"
                )
            return comp_type()

        # Handle components with fields
        if len(args) != len(field_names):
            raise ValueError(
                f"Component {comp_type.__name__} expects {len(field_names)} "
                f"arguments ({field_names}), got {len(args)}"
            )
        kwargs = dict(zip(field_names, args))
        return comp_type(**kwargs)

    # ------------------------------------------------------------------ #
    # Component operations
    # ------------------------------------------------------------------ #
    def add(self, comp_type: Type[Component], *args: Any) -> None:
        """Adds a component to the entity.

        :param comp_type: Component type (class)
        :param *args: Component field values (optional)
        :raises EntityNotEnabled: If the entity is not enabled
        :raises AlreadyAddedComponent: If the component already exists
        """
        self._ensure_enabled("add", comp_type)

        if self.has(comp_type):
            raise AlreadyAddedComponent(
                f"Cannot add another component '{comp_type.__name__}' to {self}."
            )

        new_comp = self._create_component(comp_type, *args)
        self._context.store_add(self._index, comp_type, new_comp)
        self.on_component_added(self, new_comp)

    def remove(self, comp_type: Type[Component]) -> None:
        """Removes a component from the entity.

        :param comp_type: Component type to remove
        :raises EntityNotEnabled: If the entity is not enabled
        :raises MissingComponent: If the component doesn't exist
        """
        self._ensure_enabled("remove", comp_type)

        if not self.has(comp_type):
            raise MissingComponent(
                f"Cannot remove non-existing component '{comp_type.__name__}' from {self}."
            )

        self._replace(comp_type, None)

    def replace(self, comp_type: Type[Component], *args: Any) -> None:
        """Replaces an existing component or adds it if it doesn't exist.

        :param comp_type: Component type to replace/add
        :param *args: Component field values (optional)
        :raises EntityNotEnabled: If the entity is not enabled
        """
        self._ensure_enabled("replace", comp_type)

        if self.has(comp_type):
            self._replace(comp_type, args)
        else:
            self.add(comp_type, *args)

    def _replace(self, comp_type: Type[Component], args: Any) -> None:
        previous_comp = self._context.store_get(self._index, comp_type)
        if args is None:
            self._context.store_remove(self._index, comp_type)
            self.on_component_removed(self, previous_comp)
        else:
            new_comp = self._create_component(comp_type, *args)
            self._context.store_replace(self._index, comp_type, new_comp)
            self.on_component_replaced(self, previous_comp, new_comp)

    def get(self, comp_type: Type[ComponentT]) -> ComponentT:
        """Retrieves a component by its type.

        :param comp_type: Component type to retrieve
        :return: Component instance of the specified type
        :raises MissingComponent: If the component doesn't exist
        """
        if not self.has(comp_type):
            raise MissingComponent(
                f"Cannot get non-existing component '{comp_type.__name__}' from {self}."
            )

        return cast(ComponentT, self._context.store_get(self._index, comp_type))

    def has(self, *args: Type[Component]) -> bool:
        """Checks if the entity has all components of the given type(s).

        :param args: Component types to check
        :return: True if all component types are present, False otherwise
        """
        context = self._context
        index = self._index
        return all(context.store_has(index, comp_type) for comp_type in args)

    def has_any(self, *args: Type[Component]) -> bool:
        """Checks if the entity has any component of the given type(s).

        :param args: Component types to check
        :return: True if any component type is present, False otherwise
        """
        context = self._context
        index = self._index
        return any(context.store_has(index, comp_type) for comp_type in args)

    def set(self, comp_type: Type[Component], comp_obj: Component) -> None:
        """Sets a component instance directly on the entity.

        This method allows setting a pre-created component instance,
        unlike add() which creates the component from arguments.

        :param comp_type: Component type (class)
        :param comp_obj: Pre-created component instance
        :raises EntityNotEnabled: If the entity is not enabled
        :raises AlreadyAddedComponent: If the component already exists
        """
        self._ensure_enabled("set", comp_type)

        if self.has(comp_type):
            raise AlreadyAddedComponent(
                f"Cannot set another component '{comp_type.__name__}' to {self}."
            )

        self._context.store_add(self._index, comp_type, comp_obj)
        self.on_component_added(self, comp_obj)

    def remove_all(self) -> None:
        """Removes all components from the entity."""
        for comp_type in self.component_types:
            self._replace(comp_type, None)

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def name(self) -> str:
        """Gets the entity's name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Sets the entity's name."""
        self._name = value

    @property
    def index(self) -> int:
        """Gets the entity's dense slot index inside its context."""
        return self._index

    @property
    def is_enabled(self) -> bool:
        """Whether this handle still points at a live entity.

        Derived from the context: a handle is live while the context's slot still
        holds this exact handle object.
        """
        return bool(self._context.store_is_valid(self))

    @property
    def component_count(self) -> int:
        """Gets the number of components attached to this entity."""
        return len(self._context.store_component_types(self._index))

    @property
    def component_types(self) -> Tuple[Type[Component], ...]:
        """Gets a tuple of all component types attached to this entity."""
        return tuple(self._context.store_component_types(self._index))

    def get_all_components(self) -> Tuple[Component, ...]:
        """Gets a tuple of all component instances attached to this entity."""
        return tuple(self._context.store_components(self._index))

    def iter_component_items(self) -> List[Tuple[Type[Component], Component]]:
        """Returns ``(component_type, component)`` pairs attached to this entity."""
        types = self._context.store_component_types(self._index)
        get = self._context.store_get
        return [(comp_type, get(self._index, comp_type)) for comp_type in types]

    # ------------------------------------------------------------------ #
    # Representation
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:
        """Returns a string representation of the entity.

        Format: <Entity_0 [Position(x=1, y=2, z=3)]> where ``0`` is the slot index.
        """
        component_strs = [str(comp) for comp in self.get_all_components()]
        return f"<Entity_{self._index} [{', '.join(component_strs)}]>"
