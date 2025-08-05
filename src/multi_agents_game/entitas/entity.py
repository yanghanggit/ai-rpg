"""
entitas.entity
~~~~~~~~~~~~~~
An entity is a container holding data to represent certain
objects in your application. You can add, replace or remove data
from entities.

Those containers are called 'components'. They are represented by
Pydantic BaseModel classes for enhanced functionality including
data validation, serialization, and documentation.
"""

from .event import Event
from .exceptions import EntityNotEnabled, AlreadyAddedComponent, MissingComponent
from typing import Any, Dict, Type, TypeVar, cast, Tuple
from .components import Component

# 用于泛型组件类型的类型变量，绑定到Component基类
ComponentT = TypeVar("ComponentT", bound=Component)


class Entity(object):
    """Use context.create_entity() to create a new entity and
    context.destroy_entity() to destroy it.
    You can add, replace and remove components to an entity.
    """

    def __init__(self) -> None:

        self._name = ""

        #: Occurs when a component gets added.
        self.on_component_added = Event()

        #: Occurs when a component gets removed.
        self.on_component_removed = Event()

        #: Occurs when a component gets replaced.
        self.on_component_replaced = Event()

        #: Dictionary mapping component type and component instance.
        self._components: Dict[Type[Component], Component] = {}

        #: Each entity has its own unique creationIndex which will be
        #: set by the context when you create the entity.
        self._creation_index = 0

        #: The context manages the state of an entity.
        #: Active entities are enabled, destroyed entities are not.
        self._is_enabled = False

    def activate(self, creation_index: int) -> None:
        """Activates the entity with a unique creation index.

        This method is called internally by the context when the entity
        is created. It sets the creation index and enables the entity.

        :param creation_index: Unique index assigned by the context
        """
        self._creation_index = creation_index
        self._is_enabled = True

    def _ensure_enabled(self, operation: str, comp_type: Type[Component]) -> None:
        """Ensures the entity is enabled before performing operations.

        :param operation: The operation being performed (for error messages)
        :param comp_type: The component type involved
        :raises EntityNotEnabled: If the entity is not enabled
        """
        if not self._is_enabled:
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
        self._components[comp_type] = new_comp
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
        previous_comp = self._components[comp_type]
        if args is None:
            del self._components[comp_type]
            self.on_component_removed(self, previous_comp)
        else:
            new_comp = self._create_component(comp_type, *args)
            self._components[comp_type] = new_comp
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

        return cast(ComponentT, self._components[comp_type])

    def has(self, *args: Type[Component]) -> bool:
        """Checks if the entity has all components of the given type(s).

        :param args: Component types to check
        :return: True if all component types are present, False otherwise
        """
        if len(args) == 1:
            return args[0] in self._components

        # Use generator expression for better performance
        return all(comp_type in self._components for comp_type in args)

    def has_any(self, *args: Type[Component]) -> bool:
        """Checks if the entity has any component of the given type(s).

        :param args: Component types to check
        :return: True if any component type is present, False otherwise
        """
        return any(comp_type in self._components for comp_type in args)

    def remove_all(self) -> None:
        """Removes all components from the entity."""
        for comp_type in list(self._components):
            self._replace(comp_type, None)

    def destroy(self) -> None:
        """Destroys the entity by disabling it and removing all components.

        This method is used internally. Don't call it yourself.
        Use context.destroy_entity(entity) instead.
        """
        self._is_enabled = False
        self.remove_all()

    def __repr__(self) -> str:
        """Returns a string representation of the entity.

        Format: <Entity_0 [Position(x=1, y=2, z=3)]>
        """
        component_strs = [str(comp) for comp in self._components.values()]
        return f"<Entity_{self._creation_index} [{', '.join(component_strs)}]>"

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

        self._components[comp_type] = comp_obj
        self.on_component_added(self, comp_obj)

    @property
    def name(self) -> str:
        """Gets the entity's name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Sets the entity's name."""
        self._name = value

    @property
    def creation_index(self) -> int:
        """Gets the entity's creation index."""
        return self._creation_index

    @property
    def is_enabled(self) -> bool:
        """Gets whether the entity is enabled."""
        return self._is_enabled

    @property
    def component_count(self) -> int:
        """Gets the number of components attached to this entity."""
        return len(self._components)

    @property
    def component_types(self) -> Tuple[Type[Component], ...]:
        """Gets a tuple of all component types attached to this entity."""
        return tuple(self._components.keys())

    def get_all_components(self) -> Tuple[Component, ...]:
        """Gets a tuple of all component instances attached to this entity."""
        return tuple(self._components.values())
