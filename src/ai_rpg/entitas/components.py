"""
entitas.components
~~~~~~~~~~~~~~~~~
Base classes and utilities for creating components in the ECS system.
Provides both namedtuple compatibility and Pydantic BaseModel support.
"""

from pydantic import BaseModel, ConfigDict


class Component(BaseModel):
    """Base class for all Pydantic-based components.

    This provides:
    - Automatic validation of field types
    - JSON serialization/deserialization
    - Immutability (frozen=True)
    - Documentation generation
    """

    model_config = ConfigDict(
        frozen=True,  # Makes components immutable like namedtuples
        arbitrary_types_allowed=True,  # Allows custom types if needed
        str_strip_whitespace=True,  # Auto-strip strings
        validate_assignment=True,  # Validate on assignment
    )

    def __repr__(self) -> str:
        """Custom representation that matches namedtuple style."""
        field_values = []
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, str):
                field_values.append(f"{field_name}='{field_value}'")
            else:
                field_values.append(f"{field_name}={field_value}")
        return f"{self.__class__.__name__}({', '.join(field_values)})"

    def __str__(self) -> str:
        """String representation - same as __repr__ for consistency."""
        return self.__repr__()


class MutableComponent(Component):
    """Base class for mutable components that can be modified after creation.

    While standard components are immutable (frozen) to ensure consistency,
    some special components may need to be modified in place. Use this base
    class sparingly and only when necessary, as mutable state can lead to
    harder-to-debug issues in an ECS system.

    Examples of appropriate use cases:
    - Components tracking rapid changes like positions in physics simulations
    - Components managing complex internal state that would be inefficient to recreate
    - Temporary components used for local calculations
    """

    model_config = ConfigDict(
        frozen=False,  # Override base class to allow mutability
        # Other settings are inherited from Component
    )
