from abc import ABCMeta, abstractmethod
from .exceptions import EntitasException
from typing import Any, Dict, Type, cast
from .group import Group
from .entity import Entity


class AbstractEntityIndex(metaclass=ABCMeta):

    def __init__(self, comp_type: Any, group: Group, *fields: Any) -> None:
        self.type = comp_type
        self._group = group
        self._fields = fields
        self._index: Dict[str, Any] = {}
        self._activate()

    def __del__(self) -> None:
        self._deactivate()

    def _activate(self) -> 'AbstractEntityIndex':
        self._group.on_entity_added += self._on_entity_added
        self._group.on_entity_removed += self._on_entity_removed
        self._index_entities()
        return self

    def _deactivate(self) -> None:
        self._group.on_entity_added -= self._on_entity_added
        self._group.on_entity_removed -= self._on_entity_removed
        self._index.clear()

    def _index_entities(self) -> None:
        for entity in self._group.entities:
            for field in self._fields:
                self._add_entity(getattr(entity.get(self.type), field), entity)

    def _on_entity_added(self, entity: Entity, component: Any) -> None:
        for field in self._fields:
            self._add_entity(getattr(component, field), entity)

    def _on_entity_removed(self, entity: Entity, component: Any) -> None:
        for field in self._fields:
            self._remove_entity(getattr(component, field), entity)

    @abstractmethod
    def _add_entity(self, key: str, entity: Entity) -> None:
        pass

    @abstractmethod
    def _remove_entity(self, key: str, entity: Entity) -> None:
        pass


class EntityIndex(AbstractEntityIndex):

    def get_entities(self, key: str) -> set[Entity]:
        if key not in self._index:
            self._index[key] = set()
        return cast(set[Entity], self._index[key])

    def _add_entity(self, key: str, entity: Entity) -> None:
        self.get_entities(key).add(entity)

    def _remove_entity(self, key: str, entity: Entity) -> None:
        self.get_entities(key).remove(entity)


class PrimaryEntityIndex(AbstractEntityIndex):

    def get_entity(self, key: str) -> Entity:
        return cast(Entity, self._index[key])

    def _add_entity(self, key: str, entity: Entity) -> None:
        if key in self._index:
            raise EntitasException(
                "Entity for key '{key}' already exists!".format(key=key),
                "Only one entity for a primary key is allowed.")

        self._index[key] = entity

    def _remove_entity(self, key: str, entity: Entity) -> None:
        del self._index[key]
