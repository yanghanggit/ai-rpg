"""The processor pipeline: a concrete container that runs processors in order."""

from typing import List, Union, override

from .processor_interfaces import (
    CleanupProcessor,
    ExecuteProcessor,
    InitializeProcessor,
    TearDownProcessor,
)
from .reactive_processor import ReactiveProcessor


class ProcessorPipeline(
    InitializeProcessor, ExecuteProcessor, CleanupProcessor, TearDownProcessor
):
    """A container for managing multiple processors in an organized pipeline.

    The ProcessorPipeline class allows you to group related processors together
    and execute them in the correct order: Initialize -> Execute -> Cleanup -> TearDown.
    It also supports nested pipelines and reactive processor management.
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

            if isinstance(processor, ProcessorPipeline):
                processor.activate_reactive_processors()

    def deactivate_reactive_processors(self) -> None:
        """Deactivates all reactive processors in this pipeline and nested pipelines."""
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.deactivate()

            if isinstance(processor, ProcessorPipeline):
                processor.deactivate_reactive_processors()

    def clear_reactive_processors(self) -> None:
        """Clears all collected entities from reactive processors in this pipeline and nested pipelines."""
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.clear()

            if isinstance(processor, ProcessorPipeline):
                processor.clear_reactive_processors()
