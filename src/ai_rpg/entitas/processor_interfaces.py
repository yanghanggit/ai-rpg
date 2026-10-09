"""Processor contracts (abstract interfaces) for the processor pipeline.

These are pure interfaces: they define the lifecycle hooks a processor may
implement. A single object may implement several of them; see
:class:`~ai_rpg.entitas.processor_pipeline.ProcessorPipeline` for the composite
that runs them in order.
"""

from abc import ABC, abstractmethod


class InitializeProcessor(ABC):
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


class ExecuteProcessor(ABC):
    """Base class for processors that run every frame/cycle.

    Execute processors contain the main game logic and are called
    repeatedly during the game loop.
    """

    @abstractmethod
    async def execute(self) -> None:
        """Performs the main processing logic.

        This method is called every frame/cycle of the game loop.
        """


class CleanupProcessor(ABC):
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


class TearDownProcessor(ABC):
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
