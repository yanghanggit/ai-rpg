"""Reactive processor base class.

A :class:`ReactiveProcessor` is an :class:`ExecuteProcessor` that reacts to
entity changes: it collects entities that changed according to its triggers,
filters them, and processes them in batches every cycle.
"""

from abc import abstractmethod
from typing import Dict, List

from .collector import Collector
from .context import Context
from .entity import Entity
from .group import GroupEvent
from .matcher import Matcher
from .processor_interfaces import ExecuteProcessor


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
        self._collector: Collector = self._get_collector(context)
        self._buffer: List[Entity] = []

    @abstractmethod
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        """Defines the trigger conditions for this reactive processor.

        :return: Dictionary mapping matchers to group events that should trigger this processor
        """

    @abstractmethod
    def filter(self, entity: Entity) -> bool:
        """Filters entities before processing.

        :param entity: Entity to filter
        :return: True if the entity should be processed, False otherwise
        """

    @abstractmethod
    async def react(self, entities: List[Entity]) -> None:
        """Processes the collected and filtered entities.

        :param entities: List of entities that triggered this processor and passed the filter
        """

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
