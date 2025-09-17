"""
Test components for entitas testing.
All components use Pydantic BaseModel for enhanced functionality.
"""

from src.ai_rpg.entitas.components import Component, MutableComponent


# Basic components for testing
class Position(Component):
    """Position component with x, y coordinates."""

    x: float
    y: float


class Velocity(Component):
    """Velocity component with dx, dy movement."""

    dx: float
    dy: float


class Health(Component):
    """Health component with current and max values."""

    value: int
    max_value: int

    def model_post_init(self, __context: None) -> None:
        """Validate health values after initialization."""
        if self.value < 0:
            raise ValueError("Health value must be non-negative")
        if self.max_value <= 0:
            raise ValueError("Max health must be positive")
        if self.value > self.max_value:
            raise ValueError("Health value cannot exceed max health")


class Name(Component):
    """Name component with string value."""

    value: str


class Age(Component):
    """Age component with integer value."""

    value: int


class Score(Component):
    """Score component with integer value."""

    value: int


class Damage(Component):
    """Damage component with integer value."""

    value: int


class Defense(Component):
    """Defense component with integer value."""

    value: int


# Component without fields for edge case testing
class Marker(Component):
    """Marker component without any fields."""

    pass


# Multi-field component
class Transform(Component):
    """Transform component with position, rotation and scale."""

    x: float
    y: float
    rotation: float
    scale: float


# Mutable component examples
class Counter(MutableComponent):
    """Counter component with mutable value for incremental operations."""

    value: int = 0


class ResourcePool(MutableComponent):
    """Resource pool with current and max values, demonstrates a mutable component."""

    current: int
    maximum: int

    def model_post_init(self, __context: None) -> None:
        """Validate resource values after initialization."""
        if self.current < 0:
            raise ValueError("Resource value must be non-negative")
        if self.maximum <= 0:
            raise ValueError("Maximum resource must be positive")
        if self.current > self.maximum:
            raise ValueError("Current resource cannot exceed maximum")

    def consume(self, amount: int) -> bool:
        """Consume resources from the pool if available."""
        if amount <= 0:
            raise ValueError("Consumption amount must be positive")
        if self.current >= amount:
            self.current -= amount
            return True
        return False

    def refill(self, amount: int) -> None:
        """Refill resources up to the maximum."""
        if amount <= 0:
            raise ValueError("Refill amount must be positive")
        self.current = min(self.current + amount, self.maximum)
