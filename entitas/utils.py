

from typing import Callable, List, Any

class Event(object):
    """C# events in Python."""

    def __init__(self) -> None:
        """Initialize the Event object."""
        self._listeners: List[Callable[..., None]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """Invoke the event and call all registered listeners."""
        for listener in self._listeners:
            listener(*args, **kwargs)

    def __add__(self, listener: Callable[..., None]) -> 'Event':
        """Add a listener to the event."""
        if listener not in self._listeners:
            self._listeners.append(listener)
        return self

    def __sub__(self, listener: Callable[..., None]) -> 'Event':
        """Remove a listener from the event."""
        if listener in self._listeners:
            self._listeners.remove(listener)
        return self