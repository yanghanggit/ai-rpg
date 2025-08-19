from abc import ABCMeta, abstractmethod
from typing import Dict, List, Union, override

from .collector import Collector
from .context import Context
from .entity import Entity
from .group import GroupEvent
from .matcher import Matcher


class InitializeProcessor(metaclass=ABCMeta):
    """Base class for processors that run once during pipeline initialization.

    Initialize processors are executed when the processing pipeline starts up.
    Use this for one-time setup operations like loading resources or
    initializing system state.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Performs initialization logic.

        This method is called once when the processing pipeline starts.
        """
        pass


class ExecuteProcessor(metaclass=ABCMeta):
    """Base class for processors that run every frame/cycle.

    Execute processors contain the main game logic and are called
    repeatedly during the game loop.
    """

    @abstractmethod
    async def execute(self) -> None:
        """Performs the main processing logic.

        This method is called every frame/cycle of the game loop.
        """
        pass


class CleanupProcessor(metaclass=ABCMeta):
    """Base class for processors that run cleanup operations after each cycle.

    Cleanup processors are executed after all execute processors have run.
    Use this for operations like removing expired entities or cleaning up
    temporary state.
    """

    @abstractmethod
    def cleanup(self) -> None:
        """Performs cleanup operations.

        This method is called after each execution cycle to clean up
        temporary state or perform maintenance tasks.
        """
        pass


class TearDownProcessor(metaclass=ABCMeta):
    """Base class for processors that run during application shutdown.

    TearDown processors are executed when the application or game is
    shutting down. Use this for final cleanup operations like saving
    data or releasing resources.
    """

    @abstractmethod
    def tear_down(self) -> None:
        """Performs final cleanup during shutdown.

        This method is called once when the application is shutting down.
        """
        pass


class ReactiveProcessor(ExecuteProcessor):
    """Base class for processors that react to entity changes.

    Reactive processors automatically collect entities that have changed
    according to specified triggers, filter them, and process the
    collected entities in batches.
    """

    def __init__(self, context: Context) -> None:
        """Initializes the reactive processor.

        :param context: The ECS context to monitor for entity changes
        """
        self._collector = self._get_collector(context)
        self._buffer: List[Entity] = []

    @abstractmethod
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        """Defines the trigger conditions for this reactive processor.

        :return: Dictionary mapping matchers to group events that should trigger this processor
        """
        pass

    @abstractmethod
    def filter(self, entity: Entity) -> bool:
        """Filters entities before processing.

        :param entity: Entity to filter
        :return: True if the entity should be processed, False otherwise
        """
        pass

    @abstractmethod
    async def react(self, entities: List[Entity]) -> None:
        """Processes the collected and filtered entities.

        :param entities: List of entities that triggered this processor and passed the filter
        """
        pass

    def activate(self) -> None:
        """Activates the reactive processor to start collecting entities."""
        self._collector.activate()

    def deactivate(self) -> None:
        """Deactivates the reactive processor to stop collecting entities."""
        self._collector.deactivate()

    def clear(self) -> None:
        """Clears all collected entities without processing them."""
        self._collector.clear_collected_entities()

    async def execute(self) -> None:
        """Executes the reactive processor logic.

        Collects entities, filters them, and processes them in batches.
        """
        if self._collector.collected_entities:
            for entity in self._collector.collected_entities:
                if self.filter(entity):
                    self._buffer.append(entity)

            self._collector.clear_collected_entities()

            if self._buffer:
                await self.react(self._buffer)
                self._buffer.clear()

    def _get_collector(self, context: Context) -> Collector:
        """Creates and configures a collector based on the processor's triggers.

        :param context: The ECS context to create groups from
        :return: Configured collector for this processor
        """
        trigger = self.get_trigger()
        collector = Collector()

        for matcher in trigger:
            group_event = trigger[matcher]
            group = context.get_group(matcher)
            collector.add(group, group_event)

        return collector


class Processors(
    InitializeProcessor, ExecuteProcessor, CleanupProcessor, TearDownProcessor
):
    """A container for managing multiple processors in an organized pipeline.

    The Processors class allows you to group related processors together
    and execute them in the correct order: Initialize -> Execute -> Cleanup -> TearDown.
    It also supports nested processors and reactive processor management.
    """

    def __init__(self) -> None:
        """Initializes an empty processor pipeline."""
        self._initialize_processors: List[InitializeProcessor] = []
        self._execute_processors: List[ExecuteProcessor] = []
        self._cleanup_processors: List[CleanupProcessor] = []
        self._tear_down_processors: List[TearDownProcessor] = []

    def add(
        self,
        processor: Union[
            InitializeProcessor, ExecuteProcessor, CleanupProcessor, TearDownProcessor
        ],
    ) -> None:
        """Adds a processor to the appropriate execution lists.

        A processor can implement multiple interfaces and will be added
        to all appropriate lists.

        :param processor: The processor to add to the pipeline
        """
        if isinstance(processor, InitializeProcessor):
            self._initialize_processors.append(processor)

        if isinstance(processor, ExecuteProcessor):
            self._execute_processors.append(processor)

        if isinstance(processor, CleanupProcessor):
            self._cleanup_processors.append(processor)

        if isinstance(processor, TearDownProcessor):
            self._tear_down_processors.append(processor)

    @override
    async def initialize(self) -> None:
        """Executes all initialize processors in the order they were added."""
        for processor in self._initialize_processors:
            await processor.initialize()

    @override
    async def execute(self) -> None:
        """Executes all execute processors in the order they were added."""
        for processor in self._execute_processors:
            await processor.execute()

    @override
    def cleanup(self) -> None:
        """Executes all cleanup processors in the order they were added."""
        for processor in self._cleanup_processors:
            processor.cleanup()

    @override
    def tear_down(self) -> None:
        """Executes all tear down processors in the order they were added."""
        for processor in self._tear_down_processors:
            processor.tear_down()

    def activate_reactive_processors(self) -> None:
        """Activates all reactive processors in this pipeline and nested pipelines."""
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.activate()

            if isinstance(processor, Processors):
                processor.activate_reactive_processors()

    def deactivate_reactive_processors(self) -> None:
        """Deactivates all reactive processors in this pipeline and nested pipelines."""
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.deactivate()

            if isinstance(processor, Processors):
                processor.deactivate_reactive_processors()

    def clear_reactive_processors(self) -> None:
        """Clears all collected entities from reactive processors in this pipeline and nested pipelines."""
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.clear()

            if isinstance(processor, Processors):
                processor.clear_reactive_processors()
