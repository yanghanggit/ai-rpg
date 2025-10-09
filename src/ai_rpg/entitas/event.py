"""
Utility classes for the ECS framework.

This module provides common utility classes used throughout the ECS framework,
including event handling and observer pattern implementations.
"""

from typing import Any, Callable, Iterator, List
from loguru import logger


class Event:
    """
    Observer pattern implementation mimicking C# events.

    Provides a simple event system that allows multiple listeners to subscribe
    to and receive notifications when the event is triggered. This is used
    throughout the ECS framework for component and entity lifecycle events.

    Example:
        >>> event = Event()
        >>> def handler(entity, component):
        ...     print(f"Component {component} added to {entity}")
        >>> event += handler  # Subscribe
        >>> event(entity, component)  # Trigger event
        >>> event -= handler  # Unsubscribe

    Thread Safety:
        This class is not thread-safe. If used in a multi-threaded environment,
        external synchronization is required.
    """

    def __init__(self) -> None:
        """
        Initialize the Event object.

        Creates an empty list of listeners that will be called when the event
        is triggered.
        """
        self._listeners: List[Callable[..., None]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        """
        Invoke the event and call all registered listeners.

        Calls each registered listener with the provided arguments. If a listener
        raises an exception, it will be logged but won't prevent other listeners
        from being called.

        Args:
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners

        Note:
            Listeners are called in the order they were registered.
        """
        for listener in self._listeners:
            try:
                listener(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Event listener {listener} raised exception: {e}")

    def __add__(self, listener: Callable[..., None]) -> "Event":
        """
        Add a listener to the event.

        Subscribes a callable to this event. The listener will be called
        whenever the event is triggered. Duplicate listeners are ignored.

        Args:
            listener: A callable that will be invoked when the event is triggered

        Returns:
            Self, allowing for method chaining

        Example:
            >>> event = Event()
            >>> event += my_handler
            >>> event += another_handler  # Chain multiple additions
        """
        if listener not in self._listeners:
            self._listeners.append(listener)
        return self

    def __sub__(self, listener: Callable[..., None]) -> "Event":
        """
        Remove a listener from the event.

        Unsubscribes a callable from this event. If the listener is not
        currently subscribed, this operation has no effect.

        Args:
            listener: The callable to remove from the event

        Returns:
            Self, allowing for method chaining

        Example:
            >>> event = Event()
            >>> event += my_handler
            >>> event -= my_handler  # Remove handler
        """
        if listener in self._listeners:
            self._listeners.remove(listener)
        return self

    def __len__(self) -> int:
        """
        Get the number of registered listeners.

        Returns:
            The count of currently registered listeners
        """
        return len(self._listeners)

    def __bool__(self) -> bool:
        """
        Check if the event has any listeners.

        Returns:
            True if there are registered listeners, False otherwise
        """
        return len(self._listeners) > 0

    def __iter__(self) -> Iterator[Callable[..., None]]:
        """
        Iterate over registered listeners.

        Yields:
            Each registered listener callable

        Note:
            Returns a copy of the listeners list to prevent modification
            during iteration.
        """
        return iter(self._listeners.copy())

    def __repr__(self) -> str:
        """
        Get string representation of the event.

        Returns:
            A string showing the event and number of listeners
        """
        return f"Event(listeners={len(self._listeners)})"

    @property
    def listener_count(self) -> int:
        """
        Get the number of registered listeners.

        Returns:
            The count of currently registered listeners
        """
        return len(self._listeners)

    @property
    def has_listeners(self) -> bool:
        """
        Check if the event has any listeners.

        Returns:
            True if there are registered listeners, False otherwise
        """
        return len(self._listeners) > 0

    def clear(self) -> None:
        """
        Remove all listeners from the event.

        This method clears all registered listeners, effectively resetting
        the event to its initial empty state.
        """
        self._listeners.clear()

    def add_listener(self, listener: Callable[..., None]) -> None:
        """
        Add a listener to the event (alternative to += operator).

        Args:
            listener: A callable that will be invoked when the event is triggered
        """
        self.__add__(listener)

    def remove_listener(self, listener: Callable[..., None]) -> None:
        """
        Remove a listener from the event (alternative to -= operator).

        Args:
            listener: The callable to remove from the event
        """
        self.__sub__(listener)

    def trigger(self, *args: Any, **kwargs: Any) -> None:
        """
        Trigger the event (alternative to calling the event directly).

        Args:
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners
        """
        self(*args, **kwargs)
