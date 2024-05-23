
from abc import ABCMeta, abstractmethod
from .collector import Collector
from .context import Context
from .entity import Entity
from .matcher import Matcher
from .group import GroupEvent
from typing import Any


class InitializeProcessor(metaclass=ABCMeta):
    @abstractmethod
    def initialize(self) -> None:
        pass


class ExecuteProcessor(metaclass=ABCMeta):
    @abstractmethod
    def execute(self) -> None:
        pass
    
    async def async_execute(self) -> None:
        pass


class CleanupProcessor(metaclass=ABCMeta):
    @abstractmethod
    def cleanup(self) -> None:
        pass


class TearDownProcessor(metaclass=ABCMeta):
    @abstractmethod
    def tear_down(self) -> None:
        pass


class ReactiveProcessor(ExecuteProcessor):

    def __init__(self, context: Context) -> None:
        self._collector = self._get_collector(context)
        self._buffer: list[Entity] = []

    @abstractmethod
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        pass

    @abstractmethod
    def filter(self, entity: Entity) -> bool:
        pass

    @abstractmethod
    def react(self, entities: list[Entity]) -> None:
        pass

    def activate(self) -> None:
        self._collector.activate()

    def deactivate(self) -> None:
        self._collector.deactivate()

    def clear(self) -> None:
        self._collector.clear_collected_entities()

    def execute(self) -> None:
        if self._collector.collected_entities:
            for entity in self._collector.collected_entities:
                if self.filter(entity):
                    self._buffer.append(entity)

            self._collector.clear_collected_entities()

            if self._buffer:
                self.react(self._buffer)
                self._buffer.clear()

    def _get_collector(self, context: Context) -> Collector:
        trigger = self.get_trigger()
        collector = Collector()

        for matcher in trigger:
            group_event = trigger[matcher]
            group = context.get_group(matcher)
            collector.add(group, group_event)

        return collector


class Processors(InitializeProcessor, ExecuteProcessor,
                 CleanupProcessor, TearDownProcessor):

    def __init__(self) -> None:
        self._initialize_processors: list[InitializeProcessor] = []
        self._execute_processors: list[ExecuteProcessor] = []
        self._cleanup_processors: list[CleanupProcessor] = []
        self._tear_down_processors: list[TearDownProcessor] = []

    def add(self, processor: Any) -> None:
        if isinstance(processor, InitializeProcessor):
            self._initialize_processors.append(processor)

        if isinstance(processor, ExecuteProcessor):
            self._execute_processors.append(processor)

        if isinstance(processor, CleanupProcessor):
            self._cleanup_processors.append(processor)

        if isinstance(processor, TearDownProcessor):
            self._tear_down_processors.append(processor)

    def initialize(self) -> None:
        for processor in self._initialize_processors:
            processor.initialize()

    def execute(self) -> None:
        for processor in self._execute_processors:
            processor.execute()

    def cleanup(self) -> None:
        for processor in self._cleanup_processors:
            processor.cleanup()

    def tear_down(self) -> None:
        for processor in self._tear_down_processors:
            processor.tear_down()

    def activate_reactive_processors(self) -> None:
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.activate()

            if isinstance(processor, Processors):
                processor.activate_reactive_processors()

    def deactivate_reactive_processors(self) -> None:
        for processor in self._execute_processors:
            if isinstance(processor, ReactiveProcessor):
                processor.deactivate()

            if isinstance(processor, Processors):
                processor.deactivate_reactive_processors()

    def clear_reactive_processors(self) -> None:
        for processor in self._execute_processors:
            # if issubclass(type(processor), ReactiveProcessor):
            #     processor.clear()
            
            if isinstance(processor, ReactiveProcessor):
                processor.clear()

            if isinstance(processor, Processors):
                processor.clear_reactive_processors()
