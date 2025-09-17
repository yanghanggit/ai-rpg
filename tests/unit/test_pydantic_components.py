"""
Test Pydantic BaseModel component functionality.
This tests the new Pydantic-based component system.
"""

import pytest
from src.ai_rpg.entitas import Entity, Context, Matcher
from src.ai_rpg.entitas.components import Component, MutableComponent
from tests.unit.test_components import Position, Health, Marker, Counter, ResourcePool


class TestPydanticComponents:
    """Test cases for Pydantic BaseModel components."""

    def test_component_creation_and_validation(self) -> None:
        """Test that Pydantic components are created and validated correctly."""
        entity = Entity()
        entity.activate(1)

        # Test normal component creation
        entity.add(Position, 10.0, 20.0)
        pos = entity.get(Position)
        assert pos.x == 10.0
        assert pos.y == 20.0
        assert isinstance(pos, Component)

        # Test component with validation
        entity.add(Health, 100, 150)
        health = entity.get(Health)
        assert health.value == 100
        assert health.max_value == 150

    def test_component_validation_errors(self) -> None:
        """Test that Pydantic validation works correctly."""
        entity = Entity()
        entity.activate(1)

        # Test negative health value
        with pytest.raises(ValueError, match="Health value must be non-negative"):
            entity.add(Health, -10, 100)

        # Test zero max health
        with pytest.raises(ValueError, match="Max health must be positive"):
            entity.add(Health, 50, 0)

        # Test value exceeding max health
        with pytest.raises(ValueError, match="Health value cannot exceed max health"):
            entity.add(Health, 150, 100)

    def test_component_without_fields(self) -> None:
        """Test component without fields (Marker)."""
        entity = Entity()
        entity.activate(1)

        # Should work with no arguments
        entity.add(Marker)
        assert entity.has(Marker)
        marker = entity.get(Marker)
        assert isinstance(marker, Component)

        # Should fail with arguments
        entity2 = Entity()
        entity2.activate(2)
        with pytest.raises(ValueError, match="expects no arguments"):
            entity2.add(Marker, "extra_arg")

    def test_component_wrong_argument_count(self) -> None:
        """Test error handling for wrong number of arguments."""
        entity = Entity()
        entity.activate(1)

        # Too few arguments
        with pytest.raises(ValueError, match="expects 2 arguments"):
            entity.add(Position, 10.0)

        # Too many arguments
        with pytest.raises(ValueError, match="expects 2 arguments"):
            entity.add(Position, 10.0, 20.0, 30.0)

    def test_component_serialization(self) -> None:
        """Test that Pydantic components can be serialized."""
        entity = Entity()
        entity.activate(1)

        entity.add(Position, 10.0, 20.0)
        entity.add(Health, 100, 150)

        pos = entity.get(Position)
        health = entity.get(Health)

        # Test JSON serialization
        pos_json = pos.model_dump_json()
        health_json = health.model_dump_json()

        assert '"x":10.0' in pos_json
        assert '"y":20.0' in pos_json
        assert '"value":100' in health_json
        assert '"max_value":150' in health_json

        # Test deserialization
        pos_dict = pos.model_dump()
        new_pos = Position(**pos_dict)
        assert new_pos.x == pos.x
        assert new_pos.y == pos.y

    def test_component_immutability(self) -> None:
        """Test that components are immutable (frozen)."""
        entity = Entity()
        entity.activate(1)

        entity.add(Position, 10.0, 20.0)
        pos = entity.get(Position)

        # Should not be able to modify the component
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            pos.x = 30.0

    def test_component_representation(self) -> None:
        """Test component string representation."""
        entity = Entity()
        entity.activate(1)

        entity.add(Position, 10.0, 20.0)
        entity.add(Health, 100, 150)

        pos = entity.get(Position)
        health = entity.get(Health)

        pos_str = str(pos)
        health_str = str(health)

        assert "Position" in pos_str
        assert "x=10.0" in pos_str
        assert "y=20.0" in pos_str

        assert "Health" in health_str
        assert "value=100" in health_str
        assert "max_value=150" in health_str

    def test_component_equality(self) -> None:
        """Test component equality comparison."""
        # Two components with same values should be equal
        pos1 = Position(x=10.0, y=20.0)
        pos2 = Position(x=10.0, y=20.0)
        pos3 = Position(x=15.0, y=25.0)

        assert pos1 == pos2
        assert pos1 != pos3

    def test_integration_with_context_and_groups(self) -> None:
        """Test that Pydantic components work correctly with Context and Groups."""
        context = Context()

        # Create entities with Pydantic components
        entity1 = context.create_entity()
        entity1.add(Position, 0.0, 0.0)
        entity1.add(Health, 100, 100)

        entity2 = context.create_entity()
        entity2.add(Position, 10.0, 10.0)

        # Test group functionality
        positioned_group = context.get_group(Matcher(Position))
        living_group = context.get_group(Matcher(Health))
        living_positioned_group = context.get_group(Matcher(Position, Health))

        assert len(positioned_group.entities) == 2
        assert len(living_group.entities) == 1
        assert len(living_positioned_group.entities) == 1

        # Test component access through groups
        for entity in positioned_group.entities:
            pos = entity.get(Position)
            assert isinstance(pos, Position)
            assert hasattr(pos, "x")
            assert hasattr(pos, "y")

    def test_mutable_component(self) -> None:
        """Test that MutableComponent can be modified after creation."""
        entity = Entity()
        entity.activate(1)

        # Add a mutable counter component
        entity.add(Counter, 5)
        counter = entity.get(Counter)

        # Verify it's mutable
        assert isinstance(counter, MutableComponent)

        # Test modifying the component directly
        counter.value = 10
        assert counter.value == 10

        # Verify the entity still has the same component with updated value
        updated_counter = entity.get(Counter)
        assert updated_counter is counter  # Should be the same instance
        assert updated_counter.value == 10

    def test_mutable_component_methods(self) -> None:
        """Test methods on mutable components that modify their state."""
        entity = Entity()
        entity.activate(1)

        # Add a resource pool with methods
        entity.add(ResourcePool, 50, 100)
        pool = entity.get(ResourcePool)

        # Test initial values
        assert pool.current == 50
        assert pool.maximum == 100

        # Test consume method
        success = pool.consume(20)
        assert success
        assert pool.current == 30

        # Test failed consumption
        success = pool.consume(40)
        assert not success
        assert pool.current == 30  # Should remain unchanged

        # Test refill method
        pool.refill(40)
        assert pool.current == 70

        # Test refill beyond maximum
        pool.refill(50)
        assert pool.current == 100  # Should cap at maximum

        # Test validation
        with pytest.raises(ValueError, match="Consumption amount must be positive"):
            pool.consume(-10)

        with pytest.raises(ValueError, match="Refill amount must be positive"):
            pool.refill(0)

    def test_mutable_vs_immutable_components(self) -> None:
        """Compare behavior of mutable and immutable components."""
        # Immutable component (standard Component)
        pos = Position(x=10.0, y=20.0)

        # Should not be modifiable
        with pytest.raises(Exception):
            pos.x = 30.0

        # Mutable component
        counter = Counter(value=5)

        # Should be modifiable
        counter.value = 10
        assert counter.value == 10

    def test_mutable_component_in_context(self) -> None:
        """Test that mutable components work correctly with Context and Groups."""
        context = Context()

        # Create entity with mutable component
        entity = context.create_entity()
        entity.add(Counter, 5)

        # Get component and modify it
        counter = entity.get(Counter)
        counter.value = 10

        # The group should still contain the entity with the modified component
        counter_group = context.get_group(Matcher(Counter))
        assert len(counter_group.entities) == 1

        # Check that component in the group is updated
        for e in counter_group.entities:
            c = e.get(Counter)
            assert c.value == 10
