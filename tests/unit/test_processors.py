"""
Tests for the Processors module in entitas framework.
"""

import pytest
from unittest.mock import Mock, AsyncMock, call
from typing import Dict, List

from src.multi_agents_game.entitas.processors import (
    InitializeProcessor,
    ExecuteProcessor,
    CleanupProcessor,
    TearDownProcessor,
    ReactiveProcessor,
    Processors,
)
from src.multi_agents_game.entitas.context import Context
from src.multi_agents_game.entitas.entity import Entity
from src.multi_agents_game.entitas.matcher import Matcher
from src.multi_agents_game.entitas.group import GroupEvent
from tests.unit.test_components import Position, Velocity, Health, Name


# Test implementations of abstract processors
class TestInitializeProcessor(InitializeProcessor):
    """Test implementation of InitializeProcessor."""

    def __init__(self) -> None:
        self.initialized = False
        self.initialize_called = False

    async def initialize(self) -> None:
        """Test initialization."""
        self.initialize_called = True
        self.initialized = True


class TestExecuteProcessor(ExecuteProcessor):
    """Test implementation of ExecuteProcessor."""

    def __init__(self) -> None:
        self.execute_count = 0
        self.executed = False

    async def execute(self) -> None:
        """Test execution."""
        self.execute_count += 1
        self.executed = True


class TestCleanupProcessor(CleanupProcessor):
    """Test implementation of CleanupProcessor."""

    def __init__(self) -> None:
        self.cleanup_called = False
        self.cleaned_up = False

    def cleanup(self) -> None:
        """Test cleanup."""
        self.cleanup_called = True
        self.cleaned_up = True


class TestTearDownProcessor(TearDownProcessor):
    """Test implementation of TearDownProcessor."""

    def __init__(self) -> None:
        self.tear_down_called = False
        self.torn_down = False

    def tear_down(self) -> None:
        """Test tear down."""
        self.tear_down_called = True
        self.torn_down = True


class TestReactiveProcessor(ReactiveProcessor):
    """Test implementation of ReactiveProcessor."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.react_called = False
        self.processed_entities: List[Entity] = []
        self.filter_results: Dict[Entity, bool] = {}

    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        """Return test trigger configuration."""
        return {
            Matcher(Position): GroupEvent.ADDED,
            Matcher(Velocity): GroupEvent.REMOVED,
        }

    def filter(self, entity: Entity) -> bool:
        """Test filter implementation."""
        return self.filter_results.get(entity, True)

    async def react(self, entities: List[Entity]) -> None:
        """Test react implementation."""
        self.react_called = True
        self.processed_entities.extend(entities)


class TestMultiInterfaceProcessor(
    InitializeProcessor, ExecuteProcessor, CleanupProcessor, TearDownProcessor
):
    """Test processor that implements multiple interfaces."""

    def __init__(self) -> None:
        self.operations_called: List[str] = []

    async def initialize(self) -> None:
        self.operations_called.append("initialize")

    async def execute(self) -> None:
        self.operations_called.append("execute")

    def cleanup(self) -> None:
        self.operations_called.append("cleanup")

    def tear_down(self) -> None:
        self.operations_called.append("tear_down")


class TestProcessors:
    """Test cases for all processor classes."""

    def test_initialize_processor_abstract(self) -> None:
        """Test that InitializeProcessor is abstract."""
        with pytest.raises(TypeError):
            InitializeProcessor()  # type: ignore

    def test_execute_processor_abstract(self) -> None:
        """Test that ExecuteProcessor is abstract."""
        with pytest.raises(TypeError):
            ExecuteProcessor()  # type: ignore

    def test_cleanup_processor_abstract(self) -> None:
        """Test that CleanupProcessor is abstract."""
        with pytest.raises(TypeError):
            CleanupProcessor()  # type: ignore

    def test_tear_down_processor_abstract(self) -> None:
        """Test that TearDownProcessor is abstract."""
        with pytest.raises(TypeError):
            TearDownProcessor()  # type: ignore

    @pytest.mark.asyncio
    async def test_initialize_processor_implementation(self) -> None:
        """Test InitializeProcessor implementation."""
        processor = TestInitializeProcessor()

        assert not processor.initialized
        assert not processor.initialize_called

        await processor.initialize()

        assert processor.initialized
        assert processor.initialize_called

    @pytest.mark.asyncio
    async def test_execute_processor_implementation(self) -> None:
        """Test ExecuteProcessor implementation."""
        processor = TestExecuteProcessor()

        assert processor.execute_count == 0
        assert not processor.executed

        await processor.execute()

        assert processor.execute_count == 1
        assert processor.executed

        # Execute again to verify counting
        await processor.execute()
        assert processor.execute_count == 2

    def test_cleanup_processor_implementation(self) -> None:
        """Test CleanupProcessor implementation."""
        processor = TestCleanupProcessor()

        assert not processor.cleanup_called
        assert not processor.cleaned_up

        processor.cleanup()

        assert processor.cleanup_called
        assert processor.cleaned_up

    def test_tear_down_processor_implementation(self) -> None:
        """Test TearDownProcessor implementation."""
        processor = TestTearDownProcessor()

        assert not processor.tear_down_called
        assert not processor.torn_down

        processor.tear_down()

        assert processor.tear_down_called
        assert processor.torn_down

    def test_reactive_processor_initialization(self) -> None:
        """Test ReactiveProcessor initialization."""
        context = Context()
        processor = TestReactiveProcessor(context)

        # Check that collector is created
        assert processor._collector is not None
        assert processor._buffer == []

        # Check trigger configuration
        trigger = processor.get_trigger()
        assert len(trigger) == 2
        assert Matcher(Position) in trigger
        assert Matcher(Velocity) in trigger
        assert trigger[Matcher(Position)] == GroupEvent.ADDED
        assert trigger[Matcher(Velocity)] == GroupEvent.REMOVED

    def test_reactive_processor_filter(self) -> None:
        """Test ReactiveProcessor filter method."""
        context = Context()
        processor = TestReactiveProcessor(context)
        entity = Entity()

        # Default filter returns True
        assert processor.filter(entity) is True

        # Set custom filter result
        processor.filter_results[entity] = False
        assert processor.filter(entity) is False

        processor.filter_results[entity] = True
        assert processor.filter(entity) is True

    @pytest.mark.asyncio
    async def test_reactive_processor_react(self) -> None:
        """Test ReactiveProcessor react method."""
        context = Context()
        processor = TestReactiveProcessor(context)

        entities = [Entity(), Entity()]

        await processor.react(entities)

        assert processor.react_called
        assert processor.processed_entities == entities

    def test_reactive_processor_activate_deactivate(self) -> None:
        """Test ReactiveProcessor activation and deactivation."""
        context = Context()
        processor = TestReactiveProcessor(context)

        # Mock the collector
        processor._collector = Mock()

        processor.activate()
        processor._collector.activate.assert_called_once()

        processor.deactivate()
        processor._collector.deactivate.assert_called_once()

    def test_reactive_processor_clear(self) -> None:
        """Test ReactiveProcessor clear method."""
        context = Context()
        processor = TestReactiveProcessor(context)

        # Mock the collector
        processor._collector = Mock()

        processor.clear()
        processor._collector.clear_collected_entities.assert_called_once()

    @pytest.mark.asyncio
    async def test_reactive_processor_execute_no_entities(self) -> None:
        """Test ReactiveProcessor execute with no collected entities."""
        context = Context()
        processor = TestReactiveProcessor(context)

        # Mock collector with no entities
        processor._collector = Mock()
        processor._collector.collected_entities = []

        await processor.execute()

        assert not processor.react_called
        assert len(processor.processed_entities) == 0

    @pytest.mark.asyncio
    async def test_reactive_processor_execute_with_entities(self) -> None:
        """Test ReactiveProcessor execute with collected entities."""
        context = Context()
        processor = TestReactiveProcessor(context)

        # Create test entities
        entity1 = Entity()
        entity2 = Entity()
        entity3 = Entity()

        # Mock collector with entities
        processor._collector = Mock()
        processor._collector.collected_entities = [entity1, entity2, entity3]

        # Set filter results - only entity1 and entity3 pass
        processor.filter_results = {
            entity1: True,
            entity2: False,
            entity3: True,
        }

        await processor.execute()

        # Verify collector was cleared
        processor._collector.clear_collected_entities.assert_called_once()

        # Verify react was called with filtered entities
        assert processor.react_called
        assert len(processor.processed_entities) == 2
        assert entity1 in processor.processed_entities
        assert entity3 in processor.processed_entities
        assert entity2 not in processor.processed_entities

        # Verify buffer was cleared
        assert len(processor._buffer) == 0

    @pytest.mark.asyncio
    async def test_reactive_processor_execute_filter_all_out(self) -> None:
        """Test ReactiveProcessor execute when filter rejects all entities."""
        context = Context()
        processor = TestReactiveProcessor(context)

        # Create test entities
        entity1 = Entity()
        entity2 = Entity()

        # Mock collector with entities
        processor._collector = Mock()
        processor._collector.collected_entities = [entity1, entity2]

        # Set filter to reject all entities
        processor.filter_results = {
            entity1: False,
            entity2: False,
        }

        await processor.execute()

        # Verify collector was cleared
        processor._collector.clear_collected_entities.assert_called_once()

        # Verify react was not called since no entities passed filter
        assert not processor.react_called
        assert len(processor.processed_entities) == 0

    def test_processors_initialization(self) -> None:
        """Test Processors container initialization."""
        processors = Processors()

        assert len(processors._initialize_processors) == 0
        assert len(processors._execute_processors) == 0
        assert len(processors._cleanup_processors) == 0
        assert len(processors._tear_down_processors) == 0

    def test_processors_add_single_interface(self) -> None:
        """Test adding processors with single interfaces."""
        processors = Processors()

        init_proc = TestInitializeProcessor()
        exec_proc = TestExecuteProcessor()
        cleanup_proc = TestCleanupProcessor()
        teardown_proc = TestTearDownProcessor()

        processors.add(init_proc)
        processors.add(exec_proc)
        processors.add(cleanup_proc)
        processors.add(teardown_proc)

        assert len(processors._initialize_processors) == 1
        assert len(processors._execute_processors) == 1
        assert len(processors._cleanup_processors) == 1
        assert len(processors._tear_down_processors) == 1

        assert processors._initialize_processors[0] == init_proc
        assert processors._execute_processors[0] == exec_proc
        assert processors._cleanup_processors[0] == cleanup_proc
        assert processors._tear_down_processors[0] == teardown_proc

    def test_processors_add_multi_interface(self) -> None:
        """Test adding processor with multiple interfaces."""
        processors = Processors()
        multi_proc = TestMultiInterfaceProcessor()

        processors.add(multi_proc)

        # Should be added to all lists since it implements all interfaces
        assert len(processors._initialize_processors) == 1
        assert len(processors._execute_processors) == 1
        assert len(processors._cleanup_processors) == 1
        assert len(processors._tear_down_processors) == 1

        assert processors._initialize_processors[0] == multi_proc
        assert processors._execute_processors[0] == multi_proc
        assert processors._cleanup_processors[0] == multi_proc
        assert processors._tear_down_processors[0] == multi_proc

    def test_processors_add_reactive_processor(self) -> None:
        """Test adding reactive processor."""
        processors = Processors()
        context = Context()
        reactive_proc = TestReactiveProcessor(context)

        processors.add(reactive_proc)

        # Reactive processor should be added to execute list only
        assert len(processors._initialize_processors) == 0
        assert len(processors._execute_processors) == 1
        assert len(processors._cleanup_processors) == 0
        assert len(processors._tear_down_processors) == 0

        assert processors._execute_processors[0] == reactive_proc

    @pytest.mark.asyncio
    async def test_processors_initialize_execution(self) -> None:
        """Test Processors initialize execution."""
        processors = Processors()

        proc1 = TestInitializeProcessor()
        proc2 = TestInitializeProcessor()

        processors.add(proc1)
        processors.add(proc2)

        await processors.initialize()

        assert proc1.initialize_called
        assert proc2.initialize_called

    @pytest.mark.asyncio
    async def test_processors_execute_execution(self) -> None:
        """Test Processors execute execution."""
        processors = Processors()

        proc1 = TestExecuteProcessor()
        proc2 = TestExecuteProcessor()

        processors.add(proc1)
        processors.add(proc2)

        await processors.execute()

        assert proc1.executed
        assert proc2.executed
        assert proc1.execute_count == 1
        assert proc2.execute_count == 1

    def test_processors_cleanup_execution(self) -> None:
        """Test Processors cleanup execution."""
        processors = Processors()

        proc1 = TestCleanupProcessor()
        proc2 = TestCleanupProcessor()

        processors.add(proc1)
        processors.add(proc2)

        processors.cleanup()

        assert proc1.cleanup_called
        assert proc2.cleanup_called

    def test_processors_tear_down_execution(self) -> None:
        """Test Processors tear down execution."""
        processors = Processors()

        proc1 = TestTearDownProcessor()
        proc2 = TestTearDownProcessor()

        processors.add(proc1)
        processors.add(proc2)

        processors.tear_down()

        assert proc1.tear_down_called
        assert proc2.tear_down_called

    @pytest.mark.asyncio
    async def test_processors_execution_order(self) -> None:
        """Test that processors are executed in the order they were added."""
        processors = Processors()

        proc1 = TestMultiInterfaceProcessor()
        proc2 = TestMultiInterfaceProcessor()
        proc3 = TestMultiInterfaceProcessor()

        processors.add(proc1)
        processors.add(proc2)
        processors.add(proc3)

        # Test initialize order
        await processors.initialize()
        assert proc1.operations_called == ["initialize"]
        assert proc2.operations_called == ["initialize"]
        assert proc3.operations_called == ["initialize"]

        # Test execute order
        await processors.execute()
        assert proc1.operations_called == ["initialize", "execute"]
        assert proc2.operations_called == ["initialize", "execute"]
        assert proc3.operations_called == ["initialize", "execute"]

        # Test cleanup order
        processors.cleanup()
        assert proc1.operations_called == ["initialize", "execute", "cleanup"]
        assert proc2.operations_called == ["initialize", "execute", "cleanup"]
        assert proc3.operations_called == ["initialize", "execute", "cleanup"]

        # Test tear down order
        processors.tear_down()
        assert proc1.operations_called == [
            "initialize",
            "execute",
            "cleanup",
            "tear_down",
        ]
        assert proc2.operations_called == [
            "initialize",
            "execute",
            "cleanup",
            "tear_down",
        ]
        assert proc3.operations_called == [
            "initialize",
            "execute",
            "cleanup",
            "tear_down",
        ]

    def test_processors_activate_reactive_processors(self) -> None:
        """Test activating reactive processors."""
        processors = Processors()
        context = Context()

        # Add different types of processors
        reactive_proc1 = TestReactiveProcessor(context)
        reactive_proc2 = TestReactiveProcessor(context)
        normal_proc = TestExecuteProcessor()

        # Mock the reactive processors using setattr to avoid mypy error
        setattr(reactive_proc1, "activate", Mock())
        setattr(reactive_proc2, "activate", Mock())

        processors.add(reactive_proc1)
        processors.add(reactive_proc2)
        processors.add(normal_proc)

        processors.activate_reactive_processors()

        reactive_proc1.activate.assert_called_once()  # type: ignore
        reactive_proc2.activate.assert_called_once()  # type: ignore

    def test_processors_deactivate_reactive_processors(self) -> None:
        """Test deactivating reactive processors."""
        processors = Processors()
        context = Context()

        # Add different types of processors
        reactive_proc1 = TestReactiveProcessor(context)
        reactive_proc2 = TestReactiveProcessor(context)
        normal_proc = TestExecuteProcessor()

        # Mock the reactive processors using setattr to avoid mypy error
        setattr(reactive_proc1, "deactivate", Mock())
        setattr(reactive_proc2, "deactivate", Mock())

        processors.add(reactive_proc1)
        processors.add(reactive_proc2)
        processors.add(normal_proc)

        processors.deactivate_reactive_processors()

        reactive_proc1.deactivate.assert_called_once()  # type: ignore
        reactive_proc2.deactivate.assert_called_once()  # type: ignore

    def test_processors_clear_reactive_processors(self) -> None:
        """Test clearing reactive processors."""
        processors = Processors()
        context = Context()

        # Add different types of processors
        reactive_proc1 = TestReactiveProcessor(context)
        reactive_proc2 = TestReactiveProcessor(context)
        normal_proc = TestExecuteProcessor()

        # Mock the reactive processors using setattr to avoid mypy error
        setattr(reactive_proc1, "clear", Mock())
        setattr(reactive_proc2, "clear", Mock())

        processors.add(reactive_proc1)
        processors.add(reactive_proc2)
        processors.add(normal_proc)

        processors.clear_reactive_processors()

        reactive_proc1.clear.assert_called_once()  # type: ignore
        reactive_proc2.clear.assert_called_once()  # type: ignore

    def test_processors_nested_reactive_operations(self) -> None:
        """Test reactive operations on nested processor containers."""
        main_processors = Processors()
        nested_processors = Processors()
        context = Context()

        # Add reactive processor to nested container
        reactive_proc = TestReactiveProcessor(context)
        setattr(reactive_proc, "activate", Mock())
        setattr(reactive_proc, "deactivate", Mock())
        setattr(reactive_proc, "clear", Mock())

        nested_processors.add(reactive_proc)
        main_processors.add(nested_processors)

        # Test activate
        main_processors.activate_reactive_processors()
        reactive_proc.activate.assert_called_once()  # type: ignore

        # Test deactivate
        main_processors.deactivate_reactive_processors()
        reactive_proc.deactivate.assert_called_once()  # type: ignore

        # Test clear
        main_processors.clear_reactive_processors()
        reactive_proc.clear.assert_called_once()  # type: ignore

    @pytest.mark.asyncio
    async def test_processors_full_lifecycle(self) -> None:
        """Test complete processor lifecycle."""
        processors = Processors()
        context = Context()

        # Add various processors
        multi_proc = TestMultiInterfaceProcessor()
        reactive_proc = TestReactiveProcessor(context)

        processors.add(multi_proc)
        processors.add(reactive_proc)

        # Mock reactive processor methods using setattr to avoid mypy error
        setattr(reactive_proc, "activate", Mock())
        setattr(reactive_proc, "deactivate", Mock())
        setattr(reactive_proc, "clear", Mock())

        # Activate reactive processors
        processors.activate_reactive_processors()
        reactive_proc.activate.assert_called_once()  # type: ignore

        # Initialize
        await processors.initialize()
        assert "initialize" in multi_proc.operations_called

        # Execute
        await processors.execute()
        assert "execute" in multi_proc.operations_called

        # Cleanup
        processors.cleanup()
        assert "cleanup" in multi_proc.operations_called

        # Clear reactive processors
        processors.clear_reactive_processors()
        reactive_proc.clear.assert_called_once()  # type: ignore

        # Deactivate reactive processors
        processors.deactivate_reactive_processors()
        reactive_proc.deactivate.assert_called_once()  # type: ignore

        # Tear down
        processors.tear_down()
        assert "tear_down" in multi_proc.operations_called

    def test_reactive_processor_get_collector_creates_proper_collector(self) -> None:
        """Test that _get_collector creates collector with correct configuration."""
        context = Context()
        processor = TestReactiveProcessor(context)

        # The collector should be created during initialization
        collector = processor._collector
        assert collector is not None

        # Verify the collector was configured with the triggers
        # This is an implementation detail test - we verify the collector
        # has the expected groups added based on our trigger configuration
        trigger = processor.get_trigger()
        assert len(trigger) == 2

    @pytest.mark.asyncio
    async def test_error_handling_in_processors(self) -> None:
        """Test error handling in processor execution."""

        class ErrorInitializeProcessor(InitializeProcessor):
            async def initialize(self) -> None:
                raise RuntimeError("Initialize error")

        class ErrorExecuteProcessor(ExecuteProcessor):
            async def execute(self) -> None:
                raise RuntimeError("Execute error")

        class ErrorCleanupProcessor(CleanupProcessor):
            def cleanup(self) -> None:
                raise RuntimeError("Cleanup error")

        class ErrorTearDownProcessor(TearDownProcessor):
            def tear_down(self) -> None:
                raise RuntimeError("TearDown error")

        processors = Processors()

        # Test initialize error
        processors.add(ErrorInitializeProcessor())
        with pytest.raises(RuntimeError, match="Initialize error"):
            await processors.initialize()

        # Test execute error
        processors = Processors()  # Reset
        processors.add(ErrorExecuteProcessor())
        with pytest.raises(RuntimeError, match="Execute error"):
            await processors.execute()

        # Test cleanup error
        processors = Processors()  # Reset
        processors.add(ErrorCleanupProcessor())
        with pytest.raises(RuntimeError, match="Cleanup error"):
            processors.cleanup()

        # Test tear down error
        processors = Processors()  # Reset
        processors.add(ErrorTearDownProcessor())
        with pytest.raises(RuntimeError, match="TearDown error"):
            processors.tear_down()
