from typing import Any, Tuple, Optional, Type
from .entity import Entity
from .components import Component


def get_expr_repr(expr: Optional[Tuple[Type[Component], ...]]) -> str:
    """Returns a string representation of the given component type expression.

    :param expr: A tuple of component types to be represented as a string
    :return: A comma-separated string of component names, or empty string if None
    """
    return "" if expr is None else ",".join([x.__name__ for x in expr])


class Matcher(object):
    """Represents a matcher for entities in the ECS framework.

    A matcher defines criteria for filtering entities based on their components.
    It supports three types of conditions:
    - all_of: Entity must have ALL specified components
    - any_of: Entity must have AT LEAST ONE of the specified components
    - none_of: Entity must have NONE of the specified components
    """

    def __init__(self, *args: Type[Component], **kwargs: Any) -> None:
        """Initializes a new instance of the Matcher class.

        :param *args: Component types that all entities must have (shorthand for all_of)
        :param all_of: Component types that all entities must have
        :param any_of: Component types where at least one must be present in entities
        :param none_of: Component types that must not be present in entities
        """
        # Ensure all component type collections are tuples (hashable)
        self._all: Optional[Tuple[Type[Component], ...]] = self._ensure_tuple(
            args if args else kwargs.get("all_of", None)
        )
        self._any: Optional[Tuple[Type[Component], ...]] = self._ensure_tuple(
            kwargs.get("any_of", None)
        )
        self._none: Optional[Tuple[Type[Component], ...]] = self._ensure_tuple(
            kwargs.get("none_of", None)
        )

    def _ensure_tuple(self, value: Any) -> Optional[Tuple[Type[Component], ...]]:
        """Ensures the given value is a tuple of component types or None.

        :param value: Value to convert (can be None, tuple, list, or single component type)
        :return: Tuple of component types or None
        """
        if value is None:
            return None
        elif isinstance(value, tuple):
            return value
        elif isinstance(value, list):
            return tuple(value)
        elif isinstance(value, type) and issubclass(value, Component):
            return (value,)
        else:
            # Try to convert iterable to tuple
            try:
                return tuple(value)
            except (TypeError, ValueError):
                raise TypeError(f"Invalid component type specification: {value}")

    @property
    def all_of(self) -> Optional[Tuple[Type[Component], ...]]:
        """Gets the component types that all entities must have.

        :return: Tuple of component types or None if not specified
        """
        return self._all

    @property
    def any_of(self) -> Optional[Tuple[Type[Component], ...]]:
        """Gets the component types where at least one must be present.

        :return: Tuple of component types or None if not specified
        """
        return self._any

    @property
    def none_of(self) -> Optional[Tuple[Type[Component], ...]]:
        """Gets the component types that must not be present.

        :return: Tuple of component types or None if not specified
        """
        return self._none

    def matches(self, entity: Entity) -> bool:
        """Determines if the given entity matches the matcher's conditions.

        :param entity: The entity to be checked
        :return: True if the entity matches all conditions, False otherwise
        """
        all_cond = self._all is None or entity.has(*self._all)
        any_cond = self._any is None or entity.has_any(*self._any)
        none_cond = self._none is None or not entity.has_any(*self._none)

        return all_cond and any_cond and none_cond

    def __eq__(self, other: object) -> bool:
        """Checks equality with another matcher.

        :param other: Another object to compare with
        :return: True if both matchers have the same criteria, False otherwise
        """
        if not isinstance(other, Matcher):
            return False
        return (
            self._all == other._all
            and self._any == other._any
            and self._none == other._none
        )

    def __hash__(self) -> int:
        """Returns a hash value for the matcher.

        This allows matchers to be used as dictionary keys.

        :return: Hash value based on the matcher's criteria
        """
        return hash((self._all, self._any, self._none))

    def __repr__(self) -> str:
        """Returns a string representation of the Matcher.

        :return: String representation showing all matching criteria
        """
        return f"<Matcher [all=({get_expr_repr(self._all)}) any=({get_expr_repr(self._any)}) none=({get_expr_repr(self._none)})]>"
