


from typing import Any
from entitas.entity import Entity

def get_expr_repr(expr: Any) -> str:
    """
    Returns a string representation of the given expression.

    Args:
        expr: The expression to be represented as a string.

    Returns:
        A string representation of the expression.
    """
    return '' if expr is None else ','.join([x.__name__ for x in expr])


class Matcher(object):
    """
    Represents a matcher for entities in the Entitas framework.

    Attributes:
        _all: A tuple of component types that all entities must have.
        _any: A tuple of component types where at least one must be present in entities.
        _none: A tuple of component types that must not be present in entities.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initializes a new instance of the Matcher class.

        Args:
            *args: Variable length argument list of component types that all entities must have.
            **kwargs: Keyword arguments:
                all_of: A tuple of component types that all entities must have.
                any_of: A tuple of component types where at least one must be present in entities.
                none_of: A tuple of component types that must not be present in entities.
        """
        self._all = args if args else kwargs.get('all_of', None)
        self._any = kwargs.get('any_of', None)
        self._none = kwargs.get('none_of', None)

    def matches(self, entity: Entity) -> bool:
        """
        Determines if the given entity matches the matcher's conditions.

        Args:
            entity: The entity to be checked.

        Returns:
            True if the entity matches the conditions, False otherwise.
        """
        all_cond = self._all is None or entity.has(*self._all)
        any_cond = self._any is None or entity.has_any(*self._any)
        none_cond = self._none is None or not entity.has_any(*self._none)

        return all_cond and any_cond and none_cond

    def __repr__(self) -> str:
        """
        Returns a string representation of the Matcher.

        Returns:
            A string representation of the Matcher.
        """
        return '<Matcher [all=({}) any=({}) none=({})]>'.format(
            get_expr_repr(self._all),
            get_expr_repr(self._any),
            get_expr_repr(self._none))
