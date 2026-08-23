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
    - Documentation generation
    """

    model_config = ConfigDict(
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
